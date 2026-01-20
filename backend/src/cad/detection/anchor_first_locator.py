"""
锚点优先定位器 - 先找锚点文本，再反推图框外框

流程：
1) 扫描文本实体（含块内文字）找到“主锚点”文本
2) 基于锚点ROI + 纸张拟合反推外框候选
3) 在锚点ROI内确认“次锚点”文本，满足双命中
4) 若外框为A4，则按A4规则扩展同簇外框
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ...models import BBox, FrameMeta, FrameRuntime


@dataclass(frozen=True)
class TextItem:
    x: float
    y: float
    text: str
    bbox: BBox | None
    source: str


@dataclass(frozen=True)
class CandidateFrame:
    bbox: BBox
    paper_variant_id: str
    sx: float
    sy: float
    roi_profile_id: str
    anchor_roi: BBox
    fit_error: float

    @property
    def area(self) -> float:
        return self.bbox.width * self.bbox.height


class AnchorFirstLocator:
    """锚点优先的图框定位器"""

    def __init__(
        self,
        spec,
        candidate_finder,
        paper_fitter,
        max_candidates: int | None = None,
    ) -> None:
        self.spec = spec
        self.candidate_finder = candidate_finder
        self.paper_fitter = paper_fitter
        self.paper_variants = self.spec.get_paper_variants()
        self.max_candidates = max_candidates

        anchor_cfg = self.spec.titleblock_extract.get("anchor", {})
        self.primary_text = anchor_cfg.get("primary_text")
        self.secondary_text = anchor_cfg.get("secondary_text")
        if not self.primary_text or not self.secondary_text:
            self.primary_text, self.secondary_text = self._derive_anchor_texts(
                anchor_cfg.get("search_text", ["CNPE", "中国核电工程有限公司"])
            )
        self.roi_field_name = anchor_cfg.get("roi_field_name", "锚点")
        self.match_policy = anchor_cfg.get("match_policy", "double_hit_same_roi")

        tolerances = self.spec.titleblock_extract.get("tolerances", {})
        self.roi_margin_percent = float(tolerances.get("roi_margin_percent", 0.0))

        a4_cfg = self.spec.a4_multipage.get("cluster_building", {})
        self.a4_gap_factor = float(a4_cfg.get("gap_threshold_factor", 0.5))

        self.logger = logging.getLogger(__name__)

    def locate_frames(self, msp, dxf_path: Path) -> list[FrameMeta]:
        """执行锚点优先定位，返回FrameMeta列表"""
        text_items = list(self._iter_text_items(msp))
        primary_items = [t for t in text_items if self._match_text(t.text, self.primary_text)]
        secondary_items = [t for t in text_items if self._match_text(t.text, self.secondary_text)]

        candidates = self._build_candidates(msp)
        if not candidates:
            return []

        a4_clusters = self._build_a4_clusters([c for c in candidates if self._is_a4_candidate(c)])
        a4_cluster_map = self._cluster_lookup(a4_clusters)

        frames: list[FrameMeta] = []
        used_candidates: set[tuple[float, float, float, float]] = set()

        for idx, anchor_item in enumerate(primary_items, start=1):
            matches = self._find_matching_candidates(anchor_item, secondary_items, candidates)
            if not matches:
                self.logger.warning(
                    "锚点未能反推外框: anchor_id=%s text=%s x=%.3f y=%.3f",
                    idx,
                    anchor_item.text,
                    anchor_item.x,
                    anchor_item.y,
                )
                continue

            selected = min(matches, key=lambda c: (c.fit_error, c.area))
            self._append_candidate_frame(selected, dxf_path, frames, used_candidates)

            # A4扩展：加入同簇外框（无需锚点）
            if self._is_a4_candidate(selected):
                cluster = a4_cluster_map.get(self._candidate_key(selected), [])
                for cand in cluster:
                    self._append_candidate_frame(cand, dxf_path, frames, used_candidates)

        return frames

    def _find_matching_candidates(
        self,
        anchor_item: TextItem,
        secondary_items: list[TextItem],
        candidates: list[CandidateFrame],
    ) -> list[CandidateFrame]:
        matches: list[CandidateFrame] = []
        for cand in candidates:
            if not self._text_in_roi(anchor_item, cand.anchor_roi):
                continue
            if self.match_policy == "double_hit_same_roi":
                if not self._roi_has_text(secondary_items, cand.anchor_roi):
                    continue
            elif self.match_policy == "any_hit_accept":
                pass
            matches.append(cand)
        return matches

    def _build_candidates(self, msp) -> list[CandidateFrame]:
        candidates: list[CandidateFrame] = []
        for bbox in self.candidate_finder.find_rectangles(msp):
            fit = self.paper_fitter.fit(bbox, self.paper_variants)
            if not fit:
                continue
            paper_id, sx, sy, profile_id = fit
            profile = self.spec.get_roi_profile(profile_id)
            if not profile:
                continue
            rb_offset = profile.fields.get(self.roi_field_name)
            if not rb_offset:
                continue
            anchor_roi = self._restore_roi(bbox, rb_offset, sx, sy)
            anchor_roi = self._expand_roi(anchor_roi, self.roi_margin_percent)
            fit_error = self._compute_fit_error(bbox, paper_id, sx, sy)
            candidates.append(
                CandidateFrame(
                    bbox=bbox,
                    paper_variant_id=paper_id,
                    sx=sx,
                    sy=sy,
                    roi_profile_id=profile_id,
                    anchor_roi=anchor_roi,
                    fit_error=fit_error,
                )
            )

        candidates.sort(key=lambda c: c.area, reverse=True)
        if self.max_candidates:
            candidates = candidates[: self.max_candidates]
        return candidates

    def _append_candidate_frame(
        self,
        cand: CandidateFrame,
        dxf_path: Path,
        frames: list[FrameMeta],
        used_candidates: set[tuple[float, float, float, float]],
    ) -> None:
        key = self._candidate_key(cand)
        if key in used_candidates:
            return
        used_candidates.add(key)
        frames.append(self._to_frame_meta(cand, dxf_path))

    def _to_frame_meta(self, cand: CandidateFrame, dxf_path: Path) -> FrameMeta:
        runtime = FrameRuntime(
            frame_id=str(self._uuid()),
            source_file=dxf_path,
            outer_bbox=cand.bbox,
            paper_variant_id=cand.paper_variant_id,
            sx=cand.sx,
            sy=cand.sy,
            geom_scale_factor=(cand.sx + cand.sy) / 2,
            roi_profile_id=cand.roi_profile_id,
        )
        return FrameMeta(runtime=runtime)

    @staticmethod
    def _uuid() -> str:
        import uuid

        return str(uuid.uuid4())

    @staticmethod
    def _candidate_key(cand: CandidateFrame) -> tuple[float, float, float, float]:
        return (
            round(cand.bbox.xmin, 3),
            round(cand.bbox.ymin, 3),
            round(cand.bbox.xmax, 3),
            round(cand.bbox.ymax, 3),
        )

    def _compute_fit_error(self, bbox: BBox, paper_id: str, sx: float, sy: float) -> float:
        variant = self.paper_variants.get(paper_id)
        if not variant:
            return float("inf")
        W_std = float(variant.W)
        H_std = float(variant.H)
        scale = (sx + sy) / 2
        return max(
            abs(W_std * scale - bbox.width) / max(bbox.width, 1e-9),
            abs(H_std * scale - bbox.height) / max(bbox.height, 1e-9),
        )

    def _build_a4_clusters(self, a4_candidates: list[CandidateFrame]) -> list[list[CandidateFrame]]:
        if not a4_candidates:
            return []
        n = len(a4_candidates)
        adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if self._are_neighbors(a4_candidates[i], a4_candidates[j]):
                    adj[i].append(j)
                    adj[j].append(i)
        visited = [False] * n
        clusters: list[list[CandidateFrame]] = []
        for i in range(n):
            if not visited[i]:
                cluster: list[CandidateFrame] = []
                self._dfs(i, adj, visited, a4_candidates, cluster)
                clusters.append(cluster)
        return clusters

    def _cluster_lookup(
        self, clusters: list[list[CandidateFrame]]
    ) -> dict[tuple[float, float, float, float], list[CandidateFrame]]:
        lookup: dict[tuple[float, float, float, float], list[CandidateFrame]] = {}
        for cluster in clusters:
            for cand in cluster:
                lookup[self._candidate_key(cand)] = cluster
        return lookup

    def _are_neighbors(self, c1: CandidateFrame, c2: CandidateFrame) -> bool:
        b1 = c1.bbox
        b2 = c2.bbox
        min_size = min(b1.width, b1.height, b2.width, b2.height)
        threshold = self.a4_gap_factor * min_size
        dx = max(0.0, max(b1.xmin, b2.xmin) - min(b1.xmax, b2.xmax))
        dy = max(0.0, max(b1.ymin, b2.ymin) - min(b1.ymax, b2.ymax))
        return dx < threshold and dy < threshold

    def _dfs(
        self,
        node: int,
        adj: list[list[int]],
        visited: list[bool],
        frames: list[CandidateFrame],
        cluster: list[CandidateFrame],
    ) -> None:
        visited[node] = True
        cluster.append(frames[node])
        for nxt in adj[node]:
            if not visited[nxt]:
                self._dfs(nxt, adj, visited, frames, cluster)

    @staticmethod
    def _is_a4_candidate(cand: CandidateFrame) -> bool:
        return "A4" in cand.paper_variant_id

    @staticmethod
    def _derive_anchor_texts(search_texts: Iterable[str]) -> tuple[str, str]:
        primary = ""
        secondary = ""
        for text in search_texts:
            if not text:
                continue
            if text.isascii():
                secondary = secondary or text
            else:
                primary = primary or text
        if not primary and secondary:
            primary = secondary
        if not secondary and primary:
            secondary = primary
        return primary, secondary

    @staticmethod
    def _normalize_anchor(text: str) -> str:
        return "".join(ch for ch in (text or "") if not ch.isspace())

    def _match_text(self, text: str, pattern: str) -> bool:
        if not pattern:
            return False
        normalized = self._normalize_anchor(text)
        if pattern.isascii():
            return pattern.upper() in normalized.upper()
        return pattern in normalized

    def _text_in_roi(self, item: TextItem, roi: BBox) -> bool:
        return self._point_in_bbox(item.x, item.y, roi) or (
            item.bbox is not None and roi.intersects(item.bbox)
        )

    def _roi_has_text(self, items: list[TextItem], roi: BBox) -> bool:
        return any(self._text_in_roi(item, roi) for item in items)

    @staticmethod
    def _point_in_bbox(x: float, y: float, bbox: BBox) -> bool:
        return bbox.xmin <= x <= bbox.xmax and bbox.ymin <= y <= bbox.ymax

    @staticmethod
    def _restore_roi(outer_bbox: BBox, rb_offset: list[float], sx: float, sy: float) -> BBox:
        dx_right, dx_left, dy_bottom, dy_top = rb_offset
        return BBox(
            xmin=outer_bbox.xmax - dx_left * sx,
            xmax=outer_bbox.xmax - dx_right * sx,
            ymin=outer_bbox.ymin + dy_bottom * sy,
            ymax=outer_bbox.ymin + dy_top * sy,
        )

    @staticmethod
    def _expand_roi(roi: BBox, margin_percent: float) -> BBox:
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

    @staticmethod
    def _iter_text_items(msp) -> Iterable[TextItem]:
        def add_text_entity(e, src: str) -> TextItem | None:
            tp = e.dxftype()
            if tp == "TEXT":
                text = (e.dxf.text or "").strip()
                p = e.dxf.insert
                x, y = float(p.x), float(p.y)
                bbox = AnchorFirstLocator._bbox_from_text(
                    text=text,
                    x=x,
                    y=y,
                    height=float(getattr(e.dxf, "height", 2.5) or 2.5),
                    halign=int(getattr(e.dxf, "halign", 0) or 0),
                    valign=int(getattr(e.dxf, "valign", 0) or 0),
                )
                return TextItem(x=x, y=y, text=text, bbox=bbox, source=src)
            if tp == "MTEXT":
                try:
                    text = (e.plain_text() or "").strip()
                except Exception:
                    text = (e.text or "").strip()
                p = e.dxf.insert
                x, y = float(p.x), float(p.y)
                bbox = AnchorFirstLocator._bbox_from_mtext(e, text, x, y)
                return TextItem(x=x, y=y, text=text, bbox=bbox, source=src)
            if tp == "ATTRIB":
                text = (e.dxf.text or "").strip()
                p = e.dxf.insert
                x, y = float(p.x), float(p.y)
                bbox = AnchorFirstLocator._bbox_from_text(
                    text=text,
                    x=x,
                    y=y,
                    height=float(getattr(e.dxf, "height", 2.5) or 2.5),
                    halign=int(getattr(e.dxf, "halign", 0) or 0),
                    valign=int(getattr(e.dxf, "valign", 0) or 0),
                )
                return TextItem(x=x, y=y, text=text, bbox=bbox, source=src)
            return None

        def walk_entity(ent, src_prefix: str, depth: int) -> Iterable[TextItem]:
            if depth > 8:
                return
            tp = ent.dxftype()
            if tp in {"TEXT", "MTEXT", "ATTRIB"}:
                item = add_text_entity(ent, f"{src_prefix}:{tp}")
                if item and item.text:
                    yield item
                return
            if tp == "INSERT":
                try:
                    for a in ent.attribs:
                        item = add_text_entity(a, f"{src_prefix}:attrib")
                        if item and item.text:
                            yield item
                except Exception:
                    pass
                try:
                    for ve in ent.virtual_entities():
                        yield from walk_entity(ve, f"{src_prefix}:virtual", depth + 1)
                except Exception:
                    pass

        for e in msp:
            yield from walk_entity(e, "msp", 0)

    @staticmethod
    def _bbox_from_text(
        *, text: str, x: float, y: float, height: float, halign: int, valign: int
    ) -> BBox:
        s0 = (text or "").replace(" ", "")
        w = max(1, len(s0)) * height * 0.6
        hh = height * 1.2
        if halign == 1:
            xmin, xmax = x - w / 2, x + w / 2
        elif halign == 2:
            xmin, xmax = x - w, x
        else:
            xmin, xmax = x, x + w
        if valign == 3:
            ymin, ymax = y - hh, y
        elif valign == 2:
            ymin, ymax = y - hh / 2, y + hh / 2
        else:
            ymin, ymax = y, y + hh
        return BBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)

    @staticmethod
    def _bbox_from_mtext(e, text: str, x: float, y: float) -> BBox:
        try:
            char_h = float(getattr(e.dxf, "char_height", getattr(e.dxf, "height", 2.5)))
        except Exception:
            char_h = 2.5
        lines = [ln for ln in (text or "").splitlines() if ln.strip()] or [text]
        n_lines = max(1, len(lines))
        try:
            width = float(getattr(e.dxf, "width", 0.0) or 0.0)
        except Exception:
            width = 0.0
        if width <= 0:
            width = max(len(ln) for ln in lines) * char_h * 0.6
        height = n_lines * char_h * 1.2
        ap = int(getattr(e.dxf, "attachment_point", 1) or 1)
        if ap in (1, 2, 3):  # top
            ymax = y
            ymin = y - height
        elif ap in (4, 5, 6):  # middle
            ymin = y - height / 2
            ymax = y + height / 2
        else:  # bottom
            ymin = y
            ymax = y + height
        if ap in (1, 4, 7):  # left
            xmin = x
            xmax = x + width
        elif ap in (2, 5, 8):  # center
            xmin = x - width / 2
            xmax = x + width / 2
        else:  # right
            xmin = x - width
            xmax = x
        return BBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
