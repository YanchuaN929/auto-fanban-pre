"""
数据模型层 - 定义系统核心数据结构

所有模块通过这些模型交互，实现解耦：
- Job: 任务状态与生命周期
- FrameMeta: 单个图框的运行期+图签字段
- SheetSet: A4多页成组结构
- DocContext: 文档生成上下文
"""

from .job import Job, JobStatus, JobType
from .frame import FrameMeta, FrameRuntime, TitleblockFields, BBox
from .sheet_set import SheetSet, PageInfo
from .doc_context import DocContext, GlobalDocParams, DerivedFields

__all__ = [
    "Job",
    "JobStatus",
    "JobType",
    "FrameMeta",
    "FrameRuntime",
    "TitleblockFields",
    "BBox",
    "SheetSet",
    "PageInfo",
    "DocContext",
    "GlobalDocParams",
    "DerivedFields",
]
