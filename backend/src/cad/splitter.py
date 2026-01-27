"""
图框拆分器 - 裁切输出子图

职责：
1. 按图框边界裁切DXF
2. 保持坐标不归零
3. 输出PDF和DWG

依赖：
- ezdxf: DXF操作
- ODAConverter: DXF→DWG转换
- 参数规范.yaml: pdf_margin_mm配置

测试要点：
- test_split_single_frame: 单图框裁切
- test_split_keep_coordinates: 坐标不归零
- test_split_margin: 裁切边距
- test_output_pdf_dwg: PDF+DWG输出
- test_split_sheet_set: A4多页裁切
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

import ezdxf

from ..config import get_config, load_spec
from ..interfaces import IFrameSplitter
from ..models import BBox, FrameMeta, SheetSet
from .oda_converter import ODAConverter


class FrameSplitter(IFrameSplitter):
    """图框拆分器实现"""

    def __init__(
        self,
        spec_path: str | None = None,
        oda_converter: ODAConverter | None = None,
    ):
        self.spec = load_spec(spec_path) if spec_path else load_spec()
        self.config = get_config()
        self.oda = oda_converter or ODAConverter()

        # PDF页边距
        margins = self.spec.doc_generation.get("options", {}).get("pdf_margin_mm", {})
        if isinstance(margins, dict) and "default" in margins:
            margins = margins["default"]
        self.margins = margins or {"top": 20, "bottom": 10, "left": 20, "right": 10}

    def split_frame(self, dxf_path: Path, frame: FrameMeta, output_dir: Path) -> tuple[Path, Path]:
        """拆分单个图框并输出PDF+DWG"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 计算裁切边界
        clip_bbox = self._calc_clip_bbox(frame.runtime.outer_bbox)

        # 2. 裁切DXF
        output_dxf = self._clip_dxf(dxf_path, clip_bbox, output_dir, frame)

        # 3. 输出PDF
        pdf_path = self._export_pdf(output_dxf, frame)

        # 4. 转换DWG
        dwg_path = self.oda.dxf_to_dwg(output_dxf, output_dir)

        # 5. 清理中间DXF（可选）
        # output_dxf.unlink()

        # 6. 更新frame路径
        frame.runtime.pdf_path = pdf_path
        frame.runtime.dwg_path = dwg_path

        return pdf_path, dwg_path

    def split_frames_batch(
        self,
        dxf_path: Path,
        frames: list[FrameMeta],
        output_dir: Path,
        progress_cb: Callable[[int], None] | None = None,
        progress_every: int = 5000,
    ) -> list[tuple[FrameMeta, Path, Path]]:
        """批量拆分同一DXF内的多个图框（一次读取，多框分发）"""
        if not frames:
            return []
        output_dir.mkdir(parents=True, exist_ok=True)

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        clip_infos: list[dict] = []
        for frame in frames:
            clip_bbox = self._calc_clip_bbox(frame.runtime.outer_bbox)
            internal_code = frame.titleblock.internal_code or frame.frame_id[:8]
            output_path = output_dir / f"{internal_code}.dxf"
            new_doc = ezdxf.new(dxfversion=doc.dxfversion)
            new_msp = new_doc.modelspace()
            clip_infos.append(
                {
                    "frame": frame,
                    "clip_bbox": clip_bbox,
                    "doc": new_doc,
                    "msp": new_msp,
                    "output_path": output_path,
                }
            )

        union_bbox = self._calc_union_bbox([ci["clip_bbox"] for ci in clip_infos])
        for idx, entity in enumerate(msp, start=1):
            entity_bbox = self._get_entity_bbox(entity)
            if entity_bbox and not union_bbox.intersects(entity_bbox):
                continue
            for info in clip_infos:
                clip_bbox = info["clip_bbox"]
                if entity_bbox is None or clip_bbox.intersects(entity_bbox):
                    with suppress(Exception):
                        info["msp"].add_foreign_entity(entity)
            if progress_cb and progress_every > 0 and idx % progress_every == 0:
                progress_cb(idx)

        results: list[tuple[FrameMeta, Path, Path]] = []
        for info in clip_infos:
            output_path = info["output_path"]
            info["doc"].saveas(str(output_path))

            frame = info["frame"]
            pdf_path = self._export_pdf(output_path, frame)
            dwg_path = self.oda.dxf_to_dwg(output_path, output_dir)
            frame.runtime.pdf_path = pdf_path
            frame.runtime.dwg_path = dwg_path
            results.append((frame, pdf_path, dwg_path))

        return results

    def split_sheet_set(
        self, dxf_path: Path, sheet_set: SheetSet, output_dir: Path
    ) -> tuple[Path, Path]:
        """拆分A4多页成组并输出多页PDF+DWG"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 计算所有页面的裁切边界
        clip_bboxes = [self._calc_clip_bbox(page.outer_bbox) for page in sheet_set.pages]

        # 2. 计算union bbox（所有页面的并集）
        union_bbox = self._calc_union_bbox(clip_bboxes)

        # 3. 裁切DXF（保留与任一clip_bbox相交的实体）
        master = sheet_set.master_page
        internal_code = ""
        if master and master.frame_meta:
            internal_code = master.frame_meta.titleblock.internal_code or ""

        output_dxf = self._clip_dxf_multi(
            dxf_path, clip_bboxes, union_bbox, output_dir, internal_code
        )

        # 4. 输出多页PDF
        pdf_path = self._export_multipage_pdf(output_dxf, sheet_set, output_dir)

        # 5. 转换DWG
        dwg_path = self.oda.dxf_to_dwg(output_dxf, output_dir)

        return pdf_path, dwg_path

    def _calc_clip_bbox(self, outer_bbox: BBox, margin_percent: float = 0.015) -> BBox:
        """计算裁切边界框（添加边距）"""
        margin_x = outer_bbox.width * margin_percent
        margin_y = outer_bbox.height * margin_percent

        return BBox(
            xmin=outer_bbox.xmin - margin_x,
            ymin=outer_bbox.ymin - margin_y,
            xmax=outer_bbox.xmax + margin_x,
            ymax=outer_bbox.ymax + margin_y,
        )

    def _calc_union_bbox(self, bboxes: list[BBox]) -> BBox:
        """计算边界框并集"""
        return BBox(
            xmin=min(b.xmin for b in bboxes),
            ymin=min(b.ymin for b in bboxes),
            xmax=max(b.xmax for b in bboxes),
            ymax=max(b.ymax for b in bboxes),
        )

    def _clip_dxf(
        self,
        dxf_path: Path,
        clip_bbox: BBox,
        output_dir: Path,
        frame: FrameMeta,
    ) -> Path:
        """裁切DXF（保留与clip_bbox相交的实体）"""
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        # 创建新文档
        new_doc = ezdxf.new(dxfversion=doc.dxfversion)
        new_msp = new_doc.modelspace()

        # 复制与clip_bbox相交的实体
        for entity in msp:
            entity_bbox = self._get_entity_bbox(entity)
            if entity_bbox is None or clip_bbox.intersects(entity_bbox):
                with suppress(Exception):
                    new_msp.add_foreign_entity(entity)

        # 输出文件名
        internal_code = frame.titleblock.internal_code or frame.frame_id[:8]
        output_path = output_dir / f"{internal_code}.dxf"

        new_doc.saveas(str(output_path))

        return output_path

    def _clip_dxf_multi(
        self,
        dxf_path: Path,
        clip_bboxes: list[BBox],
        union_bbox: BBox,
        output_dir: Path,
        internal_code: str,
    ) -> Path:
        """裁切DXF（保留与任一clip_bbox相交的实体）"""
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        new_doc = ezdxf.new(dxfversion=doc.dxfversion)
        new_msp = new_doc.modelspace()

        for entity in msp:
            entity_bbox = self._get_entity_bbox(entity)
            if entity_bbox and not union_bbox.intersects(entity_bbox):
                continue
            # 检查是否与任一clip_bbox相交
            for clip_bbox in clip_bboxes:
                if entity_bbox is None or clip_bbox.intersects(entity_bbox):
                    with suppress(Exception):
                        new_msp.add_foreign_entity(entity)
                    break  # 只复制一次

        output_path = output_dir / f"{internal_code or 'sheet_set'}.dxf"
        new_doc.saveas(str(output_path))

        return output_path

    def _get_entity_bbox(self, entity) -> BBox | None:
        """获取实体边界框，失败返回None"""
        try:
            if hasattr(entity, "bbox"):
                eb = entity.bbox()
                if eb:
                    return BBox(
                        xmin=eb.extmin.x,
                        ymin=eb.extmin.y,
                        xmax=eb.extmax.x,
                        ymax=eb.extmax.y,
                    )
        except Exception:
            return None
        return None

    def _export_pdf(self, dxf_path: Path, frame: FrameMeta) -> Path:
        """导出PDF"""
        # TODO: 实现PDF导出（需要使用ODA或其他方式）
        # 暂时返回占位路径
        pdf_path = dxf_path.with_suffix(".pdf")
        # pdf_path.touch()
        return pdf_path

    def _export_multipage_pdf(self, dxf_path: Path, sheet_set: SheetSet, output_dir: Path) -> Path:
        """导出多页PDF"""
        # TODO: 实现多页PDF导出
        # 优先：逐页窗口打印，再合并
        # 兜底：单页大图

        internal_code = ""
        if sheet_set.master_page and sheet_set.master_page.frame_meta:
            internal_code = sheet_set.master_page.frame_meta.titleblock.internal_code or ""

        pdf_path = output_dir / f"{internal_code or 'sheet_set'}.pdf"
        # pdf_path.touch()

        return pdf_path
