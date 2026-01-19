"""
锚点验证器 - 检查图框内是否包含CNPE文本

验证策略：
- 搜索文本实体："CNPE" 或 "中国核电工程有限公司"
- 检查文本位置是否在锚点ROI内
"""

from __future__ import annotations

import re

from ...models import BBox


class AnchorValidator:
    """锚点文本验证器"""

    def __init__(self, spec) -> None:
        self.spec = spec
        anchor_cfg = self.spec.titleblock_extract.get("anchor", {})
        self.search_texts: list[str] = anchor_cfg.get(
            "search_text", ["CNPE", "中国核电工程有限公司"]
        )
        self.profile_priority: list[str] = anchor_cfg.get("profile_priority", [])
        tolerances = self.spec.titleblock_extract.get("tolerances", {})
        self.roi_margin_percent: float = float(tolerances.get("roi_margin_percent", 0.0))

    def validate(
        self,
        msp,
        outer_bbox: BBox,
        sx: float,
        sy: float,
        roi_profile_id: str | None,
    ) -> bool:
        """
        验证图框是否包含锚点文本

        Args:
            msp: DXF模型空间
            outer_bbox: 外框BBox
            sx/sy: 缩放因子
            roi_profile_id: ROI配置ID（用于获取锚点ROI）

        Returns:
            是否通过锚点验证
        """
        profile_candidates: list[str] = []
        if roi_profile_id:
            profile_candidates.append(roi_profile_id)
        for profile_id in self.profile_priority:
            if profile_id not in profile_candidates:
                profile_candidates.append(profile_id)

        for profile_id in profile_candidates:
            profile = self.spec.get_roi_profile(profile_id)
            if not profile:
                continue
            rb_offset = profile.fields.get("锚点")
            if not rb_offset:
                continue

            anchor_bbox = self._restore_roi(outer_bbox, rb_offset, sx, sy)
            anchor_bbox = self._expand_roi(anchor_bbox, self.roi_margin_percent)

            if self._search_anchor_in_roi(msp, anchor_bbox):
                return True

        return False

    def _restore_roi(
        self, outer_bbox: BBox, rb_offset: list[float], sx: float, sy: float
    ) -> BBox:
        """根据rb_offset还原ROI的绝对坐标（含缩放）"""
        dx_right, dx_left, dy_bottom, dy_top = rb_offset
        return BBox(
            xmin=outer_bbox.xmax - dx_left * sx,
            xmax=outer_bbox.xmax - dx_right * sx,
            ymin=outer_bbox.ymin + dy_bottom * sy,
            ymax=outer_bbox.ymin + dy_top * sy,
        )

    def _expand_roi(self, roi: BBox, margin_percent: float) -> BBox:
        if margin_percent <= 0:
            return roi
        dx = roi.width * margin_percent
        dy = roi.height * margin_percent
        return BBox(
            xmin=roi.xmin - dx,
            ymin=roi.ymin - dy,
            xmax=roi.xmax + dx,
            ymax=roi.ymax + dy,
        )

    def _search_anchor_in_roi(self, msp, roi: BBox) -> bool:
        """搜索ROI内的锚点文本"""
        for entity in msp.query("TEXT MTEXT"):
            insert = self._get_insert(entity)
            if not insert:
                continue
            x, y = insert
            if not (roi.xmin <= x <= roi.xmax and roi.ymin <= y <= roi.ymax):
                continue
            text = self._get_text(entity)
            if not text:
                continue
            if self._match_anchor_text(text):
                return True
        return False

    def _get_insert(self, entity) -> tuple[float, float] | None:
        if not hasattr(entity, "dxf") or not hasattr(entity.dxf, "insert"):
            return None
        insert = entity.dxf.insert
        return float(insert.x), float(insert.y)

    def _get_text(self, entity) -> str:
        if hasattr(entity, "plain_text"):
            return entity.plain_text().strip()
        if hasattr(entity, "dxf") and hasattr(entity.dxf, "text"):
            return str(entity.dxf.text).strip()
        return ""

    def _match_anchor_text(self, text: str) -> bool:
        normalized = re.sub(r"\s+", "", text).upper()
        for anchor in self.search_texts:
            if anchor.isascii():
                if anchor.upper() in normalized:
                    return True
            else:
                if anchor in text:
                    return True
        return False
