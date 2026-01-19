"""
封面生成器 - Word文档生成

职责：
1. 打开封面模板（含内嵌Excel OLE）
2. 写入字段到指定单元格
3. 处理标题分割（中英文）
4. 导出PDF

依赖：
- python-docx: Word操作
- 参数规范.yaml: cover_bindings配置

测试要点：
- test_generate_cover_common: 通用封面生成
- test_generate_cover_1818: 1818封面生成（落点不同）
- test_title_split_cn: 中文标题分割
- test_title_split_en: 英文标题分割
- test_cover_revision_append: 版次追加模式
- test_external_code_19chars: 19位外部编码逐格写入
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..config import load_spec
from ..interfaces import GenerationError, ICoverGenerator
from .pdf_engine import PDFExporter

if TYPE_CHECKING:
    from ..models import DocContext


class CoverGenerator(ICoverGenerator):
    """封面生成器实现"""
    
    def __init__(
        self, 
        spec_path: str | None = None,
        pdf_exporter: PDFExporter | None = None,
    ):
        self.spec = load_spec(spec_path) if spec_path else load_spec()
        self.pdf_exporter = pdf_exporter or PDFExporter()
    
    def generate(self, ctx: DocContext, output_dir: Path) -> tuple[Path, Path]:
        """生成封面文档"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 选择模板
        template_path = self._get_template_path(ctx)
        if not Path(template_path).exists():
            raise GenerationError(f"封面模板不存在: {template_path}")
        
        # 2. 获取落点配置
        bindings = self.spec.get_cover_bindings(ctx.params.project_no)
        
        # 3. 准备写入数据
        data = self._prepare_data(ctx)
        
        # 4. 写入Word文档
        output_docx = output_dir / "封面.docx"
        self._write_cover(template_path, output_docx, bindings, data, ctx)
        
        # 5. 导出PDF
        output_pdf = output_dir / "封面.pdf"
        self.pdf_exporter.export_docx_to_pdf(output_docx, output_pdf)
        
        return output_docx, output_pdf
    
    def _get_template_path(self, ctx: DocContext) -> str:
        """获取模板路径"""
        variant = ctx.params.cover_variant if ctx.params.cover_variant != "通用" else ""
        return self.spec.get_template_path(
            "cover", 
            ctx.params.project_no, 
            variant
        )
    
    def _prepare_data(self, ctx: DocContext) -> dict:
        """准备写入数据"""
        params = ctx.params
        derived = ctx.derived
        
        return {
            "engineering_no": params.engineering_no,
            "subitem_no": params.subitem_no,
            "subitem_name": params.subitem_name,
            "subitem_name_en": params.subitem_name_en,  # 仅1818
            "design_phase": derived.design_phase,
            "design_phase_en": derived.design_phase_en,  # 仅1818
            "discipline": params.discipline,
            "discipline_en": derived.discipline_en,  # 仅1818
            "album_title_cn": params.album_title_cn,
            "album_title_en": params.album_title_en,  # 仅1818
            "album_code": derived.album_code,
            "album_internal_code": derived.album_internal_code,
            "cover_revision": params.cover_revision,
            "doc_status": params.doc_status,
            "cover_external_code": derived.cover_external_code,
        }
    
    def _write_cover(
        self, 
        template_path: str, 
        output_path: Path,
        bindings: dict,
        data: dict,
        ctx: DocContext,
    ) -> None:
        """写入封面文档"""
        # TODO: 实现Word+内嵌Excel写入
        # 需要使用python-docx + oletools或COM自动化
        
        # 暂时仅复制模板
        import shutil
        shutil.copy(template_path, output_path)
        
        # 实际实现需要：
        # 1. 打开docx
        # 2. 找到内嵌的Excel OLE对象
        # 3. 修改Excel中的单元格
        # 4. 处理标题分割（cn_split/en_split规则）
        # 5. 处理外部编码19位逐格写入
        # 6. 保存docx
