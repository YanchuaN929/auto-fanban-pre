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

from ..config import load_spec
from ..interfaces import DetectionError, IFrameDetector
from ..models import BBox, FrameMeta, FrameRuntime
from .detection import AnchorValidator, CandidateFinder, PaperFitter


class FrameDetector(IFrameDetector):
    """图框检测器实现"""

    def __init__(self, spec_path: str | None = None, min_frame_dim: float = 100.0):
        self.spec = load_spec(spec_path) if spec_path else load_spec()
        self.paper_variants = self.spec.get_paper_variants()
        outer_frame_cfg = self.spec.titleblock_extract.get("outer_frame", {})
        acceptance_cfg = outer_frame_cfg.get("acceptance", {})
        orthogonality_tol_deg = float(acceptance_cfg.get("orthogonality_tol_deg", 1.0))
        self.max_candidates = (
            acceptance_cfg.get("min_area_rank")
            if isinstance(acceptance_cfg.get("min_area_rank"), int)
            else None
        )
        base_profile = self.spec.get_roi_profile("BASE10")
        coord_tol = base_profile.tolerance if base_profile else 0.5

        scale_fit_cfg = self.spec.titleblock_extract.get("scale_fit", {})
        self.paper_fitter = PaperFitter(
            allow_rotation=bool(scale_fit_cfg.get("allow_rotation", True)),
            uniform_scale_required=bool(scale_fit_cfg.get("uniform_scale_required", True)),
            uniform_scale_tol=float(scale_fit_cfg.get("uniform_scale_tol", 0.02)),
            error_metric=str(scale_fit_cfg.get("fit_error_metric", "max_rel_error(W,H)")),
        )
        self.candidate_finder = CandidateFinder(
            min_dim=min_frame_dim,
            coord_tol=coord_tol,
            orthogonality_tol_deg=orthogonality_tol_deg,
        )
        self.anchor_validator = AnchorValidator(self.spec)

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
        candidates = self.candidate_finder.find_rectangles(msp)
        if self.max_candidates:
            candidates = candidates[: self.max_candidates]

        # 2. 对每个候选进行验证和拟合
        frames = []
        for bbox in candidates:
            frame = self._process_candidate(dxf_path, msp, bbox)
            if frame:
                frames.append(frame)

        return frames

    def _process_candidate(
        self,
        dxf_path: Path,
        msp,
        bbox: BBox
    ) -> FrameMeta | None:
        """处理单个候选框：拟合纸张、验证锚点"""

        # 1. 纸张尺寸拟合
        fit_result = self.paper_fitter.fit(bbox, self.paper_variants)
        if not fit_result:
            return None

        paper_id, sx, sy, profile_id = fit_result

        # 2. 锚点验证（必须命中）
        if not self.anchor_validator.validate(msp, bbox, sx, sy, profile_id):
            return None

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
