"""
图框检测子模块 - 候选矩形查找、锚点验证、纸张拟合

子模块：
- candidate_finder: 从DXF中查找闭合矩形候选
- anchor_validator: 验证锚点文本（CNPE）
- paper_fitter: 拟合标准纸张尺寸
"""

from .anchor_validator import AnchorValidator
from .candidate_finder import CandidateFinder
from .paper_fitter import PaperFitter

__all__ = [
    "CandidateFinder",
    "AnchorValidator",
    "PaperFitter",
]
