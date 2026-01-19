"""
文档生成模块 - 封面/目录/设计文件/IED计划

子模块：
- derivation: 派生字段计算
- cover: 封面生成（Word+PDF）
- catalog: 目录生成（Excel+PDF）
- design: 设计文件生成（Excel+PDF）
- ied: IED计划生成（仅Excel）
- pdf_engine: PDF导出引擎
"""

from .derivation import DerivationEngine
from .cover import CoverGenerator
from .catalog import CatalogGenerator
from .design import DesignFileGenerator
from .ied import IEDGenerator
from .pdf_engine import PDFExporter

__all__ = [
    "DerivationEngine",
    "CoverGenerator",
    "CatalogGenerator",
    "DesignFileGenerator",
    "IEDGenerator",
    "PDFExporter",
]
