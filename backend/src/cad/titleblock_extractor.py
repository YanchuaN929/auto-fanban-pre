"""
图签提取器 - 从图框中提取字段

职责：
1. 根据ROI profile还原各字段的ROI区域
2. 提取ROI内的文本
3. 解析字段值（internal_code/external_code/title等）

依赖：
- ezdxf: DXF解析
- 参数规范.yaml: roi_profiles/field_definitions

测试要点：
- test_roi_restore: ROI坐标还原
- test_extract_internal_code: 内部编码提取
- test_extract_external_code: 外部编码提取（19位）
- test_extract_title_bilingual: 中英文标题分流
- test_extract_page_info: 张数解析（共N张第M张）
- test_extract_revision_status_date: 版次/状态/日期（取列内最高y）
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import ezdxf

from ..config import load_spec
from ..interfaces import ExtractionError, ITitleblockExtractor
from ..models import BBox, FrameMeta, TitleblockFields


class TitleblockExtractor(ITitleblockExtractor):
    """图签提取器实现"""

    def __init__(self, spec_path: str | None = None):
        self.spec = load_spec(spec_path) if spec_path else load_spec()
        self.field_defs = self.spec.get_field_definitions()

    def extract_fields(self, dxf_path: Path, frame: FrameMeta) -> FrameMeta:
        """提取单个图框的图签字段"""
        if not dxf_path.exists():
            raise ExtractionError(f"DXF文件不存在: {dxf_path}")

        try:
            doc = ezdxf.readfile(str(dxf_path))
        except Exception as e:
            raise ExtractionError(f"DXF解析失败: {e}") from e

        msp = doc.modelspace()

        # 获取ROI profile
        profile = self.spec.get_roi_profile(frame.runtime.roi_profile_id or "BASE10")
        if not profile:
            raise ExtractionError(f"未找到ROI profile: {frame.runtime.roi_profile_id}")

        # 提取各字段
        raw_extracts: dict[str, Any] = {}

        for field_name, roi_offset in profile.fields.items():
            roi_bbox = self._restore_roi(
                frame.runtime.outer_bbox,
                roi_offset,
                frame.runtime.sx or 1.0,
                frame.runtime.sy or 1.0,
            )
            texts = self._extract_texts_in_roi(msp, roi_bbox)
            raw_extracts[field_name] = texts

        # 解析字段值
        titleblock = self._parse_fields(raw_extracts, frame)

        # 更新FrameMeta
        frame.titleblock = titleblock
        frame.raw_extracts = raw_extracts

        return frame

    def _restore_roi(
        self,
        outer_bbox: BBox,
        rb_offset: list[float],
        sx: float,
        sy: float,
    ) -> BBox:
        """
        还原ROI坐标
        
        rb_offset格式: [dx_right, dx_left, dy_bottom, dy_top]
        公式:
            xmin = outer_xmax - dx_left * sx
            xmax = outer_xmax - dx_right * sx
            ymin = outer_ymin + dy_bottom * sy
            ymax = outer_ymin + dy_top * sy
        """
        dx_right, dx_left, dy_bottom, dy_top = rb_offset

        return BBox(
            xmin=outer_bbox.xmax - dx_left * sx,
            xmax=outer_bbox.xmax - dx_right * sx,
            ymin=outer_bbox.ymin + dy_bottom * sy,
            ymax=outer_bbox.ymin + dy_top * sy,
        )

    def _extract_texts_in_roi(self, msp, roi: BBox) -> list[dict[str, Any]]:
        """提取ROI内的所有文本"""
        texts = []

        # 遍历TEXT和MTEXT实体
        for entity in msp.query("TEXT MTEXT"):
            try:
                # 获取文本位置
                if hasattr(entity, "dxf"):
                    if hasattr(entity.dxf, "insert"):
                        x, y = entity.dxf.insert.x, entity.dxf.insert.y
                    else:
                        continue
                else:
                    continue

                # 检查是否在ROI内
                if roi.xmin <= x <= roi.xmax and roi.ymin <= y <= roi.ymax:
                    text = entity.plain_text() if hasattr(entity, "plain_text") else str(entity.dxf.text)
                    texts.append({
                        "text": text.strip(),
                        "x": x,
                        "y": y,
                    })
            except Exception:
                continue

        # 按y坐标降序排序（高的在前）
        texts.sort(key=lambda t: -t["y"])

        return texts

    def _parse_fields(
        self,
        raw_extracts: dict[str, Any],
        frame: FrameMeta
    ) -> TitleblockFields:
        """解析字段值"""
        fields = TitleblockFields()

        # 内部编码
        fields.internal_code = self._parse_internal_code(
            raw_extracts.get("内部编码", [])
        )

        # 外部编码
        fields.external_code = self._parse_external_code(
            raw_extracts.get("外部编码", [])
        )

        # 工程号
        fields.engineering_no = self._parse_simple_field(
            raw_extracts.get("工程号", []),
            pattern=r"^\d{4}$"
        )

        # 子项号
        fields.subitem_no = self._parse_simple_field(
            raw_extracts.get("子项号", [])
        )

        # 图幅
        fields.paper_size_text = self._parse_simple_field(
            raw_extracts.get("图幅", [])
        )

        # 专业
        fields.discipline = self._parse_simple_field(
            raw_extracts.get("专业", [])
        )

        # 比例
        scale_text = self._parse_simple_field(raw_extracts.get("比例", []))
        fields.scale_text = scale_text
        if scale_text:
            match = re.match(r"^1[:：](\d+(?:\.\d+)?)$", scale_text)
            if match:
                fields.scale_denominator = float(match.group(1))

        # 张数
        page_total, page_index = self._parse_page_info(
            raw_extracts.get("张数", [])
        )
        fields.page_total = page_total
        fields.page_index = page_index

        # 标题（中英文分流）
        title_cn, title_en = self._parse_title_bilingual(
            raw_extracts.get("图纸标题", [])
        )
        fields.title_cn = title_cn
        fields.title_en = title_en

        # 版次/状态/日期（取y最高）
        fields.revision = self._parse_top_by_y(raw_extracts.get("版次", []))
        fields.status = self._parse_top_by_y(raw_extracts.get("状态", []))
        fields.date = self._parse_top_by_y(raw_extracts.get("日期", []))

        # 从internal_code提取album_code
        if fields.internal_code:
            fields.album_code = self._extract_album_code(fields.internal_code)

        return fields

    def _parse_internal_code(self, texts: list[dict]) -> str | None:
        """解析内部编码"""
        # 模式: XXXXXXX-XXXXX-XXX 或 XXXXXXX-XXXXX
        pattern = r"^[A-Z0-9]{7}-[A-Z0-9]{5}(?:-\d{3})?$"

        for item in texts:
            text = item["text"].upper().replace(" ", "")
            if re.match(pattern, text):
                return text

        return None

    def _parse_external_code(self, texts: list[dict]) -> str | None:
        """解析外部编码（19位）"""
        # 合并所有文本，去除DOC.NO等标头
        all_text = "".join(t["text"] for t in texts)
        all_text = re.sub(r"DOC\.?\s*NO\.?", "", all_text, flags=re.IGNORECASE)
        all_text = re.sub(r"[^A-Z0-9]", "", all_text.upper())

        if len(all_text) == 19:
            return all_text

        return None

    def _parse_simple_field(
        self,
        texts: list[dict],
        pattern: str | None = None
    ) -> str | None:
        """简单字段解析"""
        for item in texts:
            text = item["text"].strip()
            if not text:
                continue
            if pattern and not re.match(pattern, text):
                continue
            return text
        return None

    def _parse_page_info(self, texts: list[dict]) -> tuple[int | None, int | None]:
        """解析张数（共N张第M张）"""
        all_text = " ".join(t["text"] for t in texts)

        # 尝试完整模式
        match = re.search(r"共\s*(\d+)\s*张.*?第\s*([0-9Xx]+)\s*张", all_text)
        if match:
            total = int(match.group(1))
            idx_str = match.group(2)
            idx = 1 if idx_str.upper() == "X" else int(idx_str)
            return total, idx

        # 尝试分开解析
        total_match = re.search(r"共\s*(\d+)\s*张", all_text)
        idx_match = re.search(r"第\s*([0-9Xx]+)\s*张", all_text)

        total = int(total_match.group(1)) if total_match else None
        idx = None
        if idx_match:
            idx_str = idx_match.group(1)
            idx = 1 if idx_str.upper() == "X" else int(idx_str)

        return total, idx

    def _parse_title_bilingual(
        self,
        texts: list[dict]
    ) -> tuple[str | None, str | None]:
        """解析中英文标题（按y聚类分流）"""
        if not texts:
            return None, None

        # 按y坐标聚类成行
        lines = self._cluster_by_y(texts)

        cn_lines = []
        en_lines = []

        for line_texts in lines:
            line = " ".join(t["text"] for t in line_texts)
            if self._has_cjk(line):
                cn_lines.append(line)
            else:
                en_lines.append(line)

        title_cn = " ".join(cn_lines) if cn_lines else None
        title_en = " ".join(en_lines) if en_lines else None

        return title_cn, title_en

    def _cluster_by_y(self, texts: list[dict], tolerance: float = 2.0) -> list[list[dict]]:
        """按y坐标聚类"""
        if not texts:
            return []

        sorted_texts = sorted(texts, key=lambda t: -t["y"])
        lines = []
        current_line = [sorted_texts[0]]
        current_y = sorted_texts[0]["y"]

        for text in sorted_texts[1:]:
            if abs(text["y"] - current_y) <= tolerance:
                current_line.append(text)
            else:
                lines.append(current_line)
                current_line = [text]
                current_y = text["y"]

        if current_line:
            lines.append(current_line)

        return lines

    def _has_cjk(self, text: str) -> bool:
        """检查是否含有CJK字符"""
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                return True
        return False

    def _parse_top_by_y(self, texts: list[dict]) -> str | None:
        """取y值最大的文本"""
        if not texts:
            return None

        # 已按y降序排序，取第一个非空
        for item in texts:
            text = item["text"].strip()
            if text:
                return text
        return None

    def _extract_album_code(self, internal_code: str) -> str | None:
        """从internal_code提取album_code（中间5位的末2位）"""
        # 格式: XXXXXXX-XXXXX-XXX
        parts = internal_code.split("-")
        if len(parts) >= 2:
            mid5 = parts[1]
            if len(mid5) >= 2:
                return mid5[-2:]
        return None
