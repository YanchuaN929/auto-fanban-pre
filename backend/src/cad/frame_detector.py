"""
图框检测器 - 识别DXF中的图框

职责：
1. 解析DXF找到候选矩形（闭合polyline优先，LINE重建兜底）
2. 锚点验证（CNPE/中国核电工程有限公司）
3. 纸张尺寸拟合（确定paper_variant/sx/sy/roi_profile）

依赖：
- ezdxf: DXF解析
- 参数规范.yaml: paper_variants/roi_profiles/anchor配置

测试要点：
- test_detect_single_frame: 单图框检测
- test_detect_multiple_frames: 多图框检测（同一DXF内）
- test_paper_fitting: 纸张尺寸拟合（各种图幅）
- test_anchor_verification: 锚点验证
- test_scale_mismatch_flag: 比例不一致标记
"""

from __future__ import annotations

import uuid
from pathlib import Path

import ezdxf
from ezdxf.entities import LWPolyline, Polyline

from ..config import load_spec
from ..interfaces import DetectionError, IFrameDetector
from ..models import BBox, FrameMeta, FrameRuntime


class FrameDetector(IFrameDetector):
    """图框检测器实现"""
    
    def __init__(self, spec_path: str | None = None):
        self.spec = load_spec(spec_path) if spec_path else load_spec()
        self.paper_variants = self.spec.get_paper_variants()
    
    def detect_frames(self, dxf_path: Path) -> list[FrameMeta]:
        """检测DXF中的所有图框"""
        if not dxf_path.exists():
            raise DetectionError(f"DXF文件不存在: {dxf_path}")
        
        try:
            doc = ezdxf.readfile(str(dxf_path))
        except Exception as e:
            raise DetectionError(f"DXF解析失败: {e}") from e
        
        msp = doc.modelspace()
        
        # 1. 找到候选矩形
        candidates = self._find_candidate_rectangles(msp)
        
        # 2. 对每个候选进行验证和拟合
        frames = []
        for bbox in candidates:
            frame = self._process_candidate(dxf_path, doc, bbox)
            if frame:
                frames.append(frame)
        
        return frames
    
    def _find_candidate_rectangles(self, msp) -> list[BBox]:
        """找到候选矩形（闭合polyline优先）"""
        candidates = []
        
        # 优先检查闭合polyline
        for entity in msp.query("LWPOLYLINE"):
            if entity.closed:
                bbox = self._get_polyline_bbox(entity)
                if bbox and self._is_valid_frame_size(bbox):
                    candidates.append(bbox)
        
        # 如果没找到，尝试LINE重建
        if not candidates:
            candidates = self._rebuild_from_lines(msp)
        
        # 按面积排序（大的在前）
        candidates.sort(key=lambda b: b.width * b.height, reverse=True)
        
        return candidates
    
    def _get_polyline_bbox(self, entity: LWPolyline) -> BBox | None:
        """获取polyline的边界框"""
        try:
            points = list(entity.get_points())
            if len(points) < 4:
                return None
            
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            
            return BBox(
                xmin=min(xs),
                ymin=min(ys),
                xmax=max(xs),
                ymax=max(ys),
            )
        except Exception:
            return None
    
    def _rebuild_from_lines(self, msp) -> list[BBox]:
        """从LINE实体重建矩形（兜底方案）"""
        # TODO: 实现LINE重建逻辑
        return []
    
    def _is_valid_frame_size(self, bbox: BBox) -> bool:
        """检查是否为有效的图框尺寸"""
        # 最小尺寸检查（避免小矩形）
        min_dim = 100  # mm
        if bbox.width < min_dim or bbox.height < min_dim:
            return False
        return True
    
    def _process_candidate(
        self, 
        dxf_path: Path, 
        doc, 
        bbox: BBox
    ) -> FrameMeta | None:
        """处理单个候选框：验证锚点、拟合纸张"""
        
        # 1. 锚点验证
        if not self._verify_anchor(doc, bbox):
            return None
        
        # 2. 纸张尺寸拟合
        fit_result = self._fit_paper_size(bbox)
        if not fit_result:
            return None
        
        paper_id, sx, sy, profile_id = fit_result
        
        # 3. 构建FrameMeta
        runtime = FrameRuntime(
            frame_id=str(uuid.uuid4()),
            source_file=dxf_path,
            outer_bbox=bbox,
            paper_variant_id=paper_id,
            sx=sx,
            sy=sy,
            geom_scale_factor=(sx + sy) / 2,
            roi_profile_id=profile_id,
        )
        
        return FrameMeta(runtime=runtime)
    
    def _verify_anchor(self, doc, bbox: BBox) -> bool:
        """验证锚点ROI（CNPE/中国核电工程有限公司）"""
        # TODO: 实现锚点验证逻辑
        # 根据 spec.titleblock_extract.anchor 配置
        return True  # 暂时跳过验证
    
    def _fit_paper_size(
        self, 
        bbox: BBox
    ) -> tuple[str, float, float, str] | None:
        """
        拟合标准纸张尺寸
        
        Returns:
            (paper_variant_id, sx, sy, roi_profile_id) or None
        """
        W_obs = bbox.width
        H_obs = bbox.height
        
        best_match = None
        best_error = float("inf")
        
        for variant_id, variant in self.paper_variants.items():
            # 尝试正向匹配
            sx = W_obs / variant.W
            sy = H_obs / variant.H
            error = abs(sx - sy) / max(sx, sy, 1e-9)
            
            if error < 0.02 and error < best_error:  # 2% 容差
                best_error = error
                best_match = (variant_id, sx, sy, variant.profile)
            
            # 尝试旋转匹配（W↔H）
            sx_rot = W_obs / variant.H
            sy_rot = H_obs / variant.W
            error_rot = abs(sx_rot - sy_rot) / max(sx_rot, sy_rot, 1e-9)
            
            if error_rot < 0.02 and error_rot < best_error:
                best_error = error_rot
                best_match = (variant_id, sx_rot, sy_rot, variant.profile)
        
        return best_match
