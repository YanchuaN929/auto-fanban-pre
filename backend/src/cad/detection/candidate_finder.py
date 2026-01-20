"""
候选矩形查找器 - 从DXF模型空间提取闭合矩形

策略：
1. 优先: LWPOLYLINE/POLYLINE（闭合）
2. 兜底: LINE实体重建矩形（纯几何，无图层依赖）
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from ...models import BBox


class CandidateFinder:
    """候选图框查找器"""

    def __init__(
        self,
        min_dim: float = 100.0,
        coord_tol: float = 0.5,
        orthogonality_tol_deg: float = 1.0,
    ) -> None:
        self.min_dim = min_dim
        self.coord_tol = coord_tol
        self.orthogonality_tol_deg = orthogonality_tol_deg
        self._sin_tol = math.sin(math.radians(orthogonality_tol_deg))

    def find_rectangles(self, msp) -> list[BBox]:
        """
        从模型空间提取所有候选矩形

        Args:
            msp: DXF模型空间

        Returns:
            候选矩形的BBox列表（按面积降序）
        """
        candidates: list[BBox] = []

        # 1. 从LWPOLYLINE提取
        for entity in msp.query("LWPOLYLINE"):
            if entity.closed:
                bbox = self._extract_bbox(entity)
                if bbox and self._is_valid_size(bbox):
                    candidates.append(bbox)

        # 2. 从POLYLINE提取
        for entity in msp.query("POLYLINE"):
            if getattr(entity, "is_closed", False):
                bbox = self._extract_bbox(entity)
                if bbox and self._is_valid_size(bbox):
                    candidates.append(bbox)

        # 3. LINE重建矩形（兜底策略）
        if not candidates:
            candidates.extend(self._rebuild_from_lines(msp))

        # 按面积降序排序
        candidates.sort(key=lambda b: b.width * b.height, reverse=True)

        return candidates

    def _extract_bbox(self, entity) -> BBox | None:
        """从polyline提取外接矩形"""
        try:
            vertices = list(entity.get_points())
            if len(vertices) < 4:
                return None

            if not self._is_axis_aligned(vertices):
                return None

            xs = [p[0] for p in vertices]
            ys = [p[1] for p in vertices]

            return BBox(
                xmin=min(xs),
                ymin=min(ys),
                xmax=max(xs),
                ymax=max(ys),
            )
        except Exception:
            return None

    def _is_axis_aligned(self, vertices: Iterable[tuple[float, float, *tuple]]) -> bool:
        """判断polyline是否为轴对齐矩形"""
        xs = self._cluster_coords([p[0] for p in vertices])
        ys = self._cluster_coords([p[1] for p in vertices])
        return len(xs) == 2 and len(ys) == 2

    def _cluster_coords(self, values: list[float]) -> list[float]:
        """按容差聚类坐标值"""
        if not values:
            return []
        values = sorted(values)
        clusters = [[values[0]]]
        for v in values[1:]:
            if abs(v - clusters[-1][-1]) <= self.coord_tol:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [sum(c) / len(c) for c in clusters]

    def _is_valid_size(self, bbox: BBox) -> bool:
        return bbox.width >= self.min_dim and bbox.height >= self.min_dim

    def _rebuild_from_lines(self, msp) -> list[BBox]:
        """从LINE实体重建矩形（兜底方案）"""
        horizontal: list[tuple[float, float, float]] = []
        vertical: list[tuple[float, float, float]] = []

        for entity in msp.query("LINE"):
            start = entity.dxf.start
            end = entity.dxf.end
            x1, y1 = float(start.x), float(start.y)
            x2, y2 = float(end.x), float(end.y)
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)
            if length <= 0:
                continue

            if abs(dy) <= self.coord_tol or abs(dy) / length <= self._sin_tol:
                y = (y1 + y2) / 2.0
                left, right = sorted([x1, x2])
                horizontal.append((y, left, right))
            elif abs(dx) <= self.coord_tol or abs(dx) / length <= self._sin_tol:
                x = (x1 + x2) / 2.0
                bottom, top = sorted([y1, y2])
                vertical.append((x, bottom, top))

        h_segments = self._cluster_segments(horizontal)
        v_segments = self._cluster_segments(vertical)

        rectangles: list[BBox] = []
        seen: set[tuple[float, float, float, float]] = set()

        ys = sorted(h_segments.keys())
        xs = sorted(v_segments.keys())

        for yi, y1 in enumerate(ys):
            for y2 in ys[yi + 1 :]:
                if (y2 - y1) < self.min_dim:
                    continue
                for xi, x1 in enumerate(xs):
                    for x2 in xs[xi + 1 :]:
                        if (x2 - x1) < self.min_dim:
                            continue
                        if not self._has_edge(h_segments[y1], x1, x2):
                            continue
                        if not self._has_edge(h_segments[y2], x1, x2):
                            continue
                        if not self._has_edge(v_segments[x1], y1, y2):
                            continue
                        if not self._has_edge(v_segments[x2], y1, y2):
                            continue
                        key = (
                            round(x1, 3),
                            round(y1, 3),
                            round(x2, 3),
                            round(y2, 3),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        rectangles.append(BBox(xmin=x1, ymin=y1, xmax=x2, ymax=y2))

        return rectangles

    def _cluster_segments(
        self, segments: list[tuple[float, float, float]]
    ) -> dict[float, list[tuple[float, float]]]:
        """按主坐标聚类线段并合并区间"""
        if not segments:
            return {}
        segments.sort(key=lambda s: s[0])
        clusters: list[dict[str, object]] = []
        for coord, start, end in segments:
            if not clusters or abs(coord - clusters[-1]["coord"]) > self.coord_tol:
                clusters.append({"coord": coord, "count": 1, "segments": [(start, end)]})
            else:
                cluster = clusters[-1]
                cluster["segments"].append((start, end))
                count = cluster["count"] + 1
                cluster["coord"] = (cluster["coord"] * cluster["count"] + coord) / count
                cluster["count"] = count

        merged: dict[float, list[tuple[float, float]]] = {}
        for cluster in clusters:
            coord = float(cluster["coord"])
            intervals = self._merge_intervals(cluster["segments"])
            merged[coord] = intervals
        return merged

    def _merge_intervals(self, segments: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if not segments:
            return []
        sorted_segments = sorted((min(a, b), max(a, b)) for a, b in segments)
        merged = [[sorted_segments[0][0], sorted_segments[0][1]]]
        for start, end in sorted_segments[1:]:
            if start <= merged[-1][1] + self.coord_tol:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        return [(seg[0], seg[1]) for seg in merged]

    def _has_edge(self, intervals: list[tuple[float, float]], start: float, end: float) -> bool:
        for seg_start, seg_end in intervals:
            if seg_start <= start + self.coord_tol and seg_end >= end - self.coord_tol:
                return True
        return False
