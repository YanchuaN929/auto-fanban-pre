"""
流水线模块 - 任务编排与执行

子模块：
- stages: 流水线各阶段定义
- executor: 流水线执行器
- job_manager: 任务管理
- packager: 打包与manifest生成
"""

from .stages import PipelineStage, DELIVERABLE_STAGES
from .executor import PipelineExecutor
from .job_manager import JobManager
from .packager import Packager

__all__ = [
    "PipelineStage",
    "DELIVERABLE_STAGES",
    "PipelineExecutor",
    "JobManager",
    "Packager",
]
