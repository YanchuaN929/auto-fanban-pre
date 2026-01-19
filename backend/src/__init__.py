"""
CNPE 图纸处理系统 - 后端核心模块

模块结构：
- config/     配置加载与规范解析
- models/     数据模型定义
- cad/        CAD 处理（DXF解析/图框检测/字段提取）
- doc_gen/    文档生成（封面/目录/设计文件/IED）
- pipeline/   流水线编排与任务管理
- api/        FastAPI 接口层
"""

__version__ = "0.1.0"
