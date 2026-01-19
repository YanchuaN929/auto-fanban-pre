"""
派生字段单元测试

每个模块完成后必须运行：pytest tests/unit/test_derivation.py -v
"""

import pytest

from src.doc_gen.derivation import DerivationEngine
from src.models import DocContext, GlobalDocParams


class TestDerivationEngine:
    """派生字段引擎测试"""
    
    @pytest.fixture
    def engine(self) -> DerivationEngine:
        return DerivationEngine()
    
    def test_derive_album_internal_code(
        self, engine: DerivationEngine, sample_doc_context: DocContext
    ):
        """测试图册编号派生"""
        derived = engine.compute(sample_doc_context)
        
        # internal_code_001 = "1234567-JG001-001"
        # album_internal_code = "1234567-JG001"
        assert derived.album_internal_code == "1234567-JG001"
    
    def test_derive_cover_catalog_codes(
        self, engine: DerivationEngine, sample_doc_context: DocContext
    ):
        """测试封面/目录编码派生"""
        derived = engine.compute(sample_doc_context)
        
        # cover_internal_code = "1234567-JG001-FM"
        # catalog_internal_code = "1234567-JG001-TM"
        assert derived.cover_internal_code == "1234567-JG001-FM"
        assert derived.catalog_internal_code == "1234567-JG001-TM"
    
    def test_derive_external_codes(
        self, engine: DerivationEngine, sample_doc_context: DocContext
    ):
        """测试外部编码派生"""
        derived = engine.compute(sample_doc_context)
        
        # external_code_001 = "JD1NHT11001B25C42SD"
        # cover: 第9-11位(001)替换为F01
        # catalog: 第9-11位(001)替换为T01
        assert derived.cover_external_code == "JD1NHT11F01B25C42SD"
        assert derived.catalog_external_code == "JD1NHT11T01B25C42SD"
    
    def test_derive_titles(
        self, engine: DerivationEngine, sample_doc_context: DocContext
    ):
        """测试标题派生"""
        derived = engine.compute(sample_doc_context)
        
        # album_title_cn = "测试图册"
        assert derived.cover_title_cn == "测试图册封面"
        assert derived.catalog_title_cn == "测试图册目录"
    
    def test_derive_design_phase(
        self, engine: DerivationEngine, sample_doc_context: DocContext
    ):
        """测试设计阶段派生"""
        derived = engine.compute(sample_doc_context)
        
        # doc_status = "CFC" -> design_phase = "施工图设计"
        assert derived.design_phase == "施工图设计"
    
    def test_derive_1818_english(self, engine: DerivationEngine):
        """测试1818项目英文派生"""
        params = GlobalDocParams(
            project_no="1818",
            discipline="结构",
            doc_status="CFC",
            album_title_cn="测试图册",
            album_title_en="Test Album",
        )
        ctx = DocContext(params=params, frames=[])
        
        derived = engine.compute(ctx)
        
        # 1818专用英文
        assert derived.discipline_en == "Structural"
        assert derived.design_phase_en == "Constructing Design"
        assert derived.cover_title_en == "Test Album Cover"
        assert derived.catalog_title_en == "Test Album Contents"
    
    def test_derive_catalog_revision(self, engine: DerivationEngine):
        """测试目录版次派生"""
        # 有升版版本时优先
        params = GlobalDocParams(
            project_no="2016",
            cover_revision="A",
            upgrade_revision="B",
        )
        ctx = DocContext(params=params, frames=[])
        derived = engine.compute(ctx)
        assert derived.catalog_revision == "B"
        
        # 无升版版本时取封面版次
        params2 = GlobalDocParams(
            project_no="2016",
            cover_revision="A",
        )
        ctx2 = DocContext(params=params2, frames=[])
        derived2 = engine.compute(ctx2)
        assert derived2.catalog_revision == "A"
