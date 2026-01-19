"""
流水线执行器 - 编排各阶段执行

职责：
1. 按顺序执行各阶段
2. 更新任务进度
3. 处理错误和失败隔离
4. 生成manifest

测试要点：
- test_execute_full_pipeline: 完整流水线执行
- test_stage_failure_handling: 阶段失败处理
- test_progress_tracking: 进度跟踪
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ..cad import (
    A4MultipageGrouper,
    FrameDetector,
    FrameSplitter,
    ODAConverter,
    TitleblockExtractor,
)
from ..config import get_config, load_spec
from ..doc_gen import (
    CatalogGenerator,
    CoverGenerator,
    DerivationEngine,
    DesignFileGenerator,
    IEDGenerator,
)
from ..models import DocContext, GlobalDocParams
from .packager import Packager
from .stages import DELIVERABLE_STAGES, StageEnum

if TYPE_CHECKING:
    from ..models import FrameMeta, Job, SheetSet

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """流水线执行器"""
    
    def __init__(self):
        self.config = get_config()
        self.spec = load_spec()
        
        # 初始化各模块（惰性加载也可）
        self.oda = ODAConverter()
        self.frame_detector = FrameDetector()
        self.titleblock_extractor = TitleblockExtractor()
        self.a4_grouper = A4MultipageGrouper()
        self.splitter = FrameSplitter()
        self.derivation = DerivationEngine()
        self.cover_gen = CoverGenerator()
        self.catalog_gen = CatalogGenerator()
        self.design_gen = DesignFileGenerator()
        self.ied_gen = IEDGenerator()
        self.packager = Packager()
    
    def execute(self, job: Job) -> None:
        """执行流水线"""
        job.mark_running()
        
        try:
            # 设置工作目录
            job.work_dir = self.config.get_job_dir(job.job_id)
            job.work_dir.mkdir(parents=True, exist_ok=True)
            
            # 中间数据存储
            context = {
                "dxf_files": [],
                "frames": [],
                "sheet_sets": [],
            }
            
            for stage in DELIVERABLE_STAGES:
                self._execute_stage(job, stage, context)
            
            job.mark_succeeded()
            
        except Exception as e:
            logger.exception(f"流水线执行失败: {job.job_id}")
            job.mark_failed(str(e))
            raise
    
    def _execute_stage(self, job: Job, stage, context: dict) -> None:
        """执行单个阶段"""
        job.progress.stage = stage.name
        job.progress.percent = stage.progress_start
        logger.info(f"[{job.job_id}] 开始阶段: {stage.name}")
        
        try:
            if stage.name == StageEnum.INGEST.value:
                self._stage_ingest(job, context)
            
            elif stage.name == StageEnum.CONVERT_DWG_TO_DXF.value:
                self._stage_convert(job, context)
            
            elif stage.name == StageEnum.DETECT_FRAMES.value:
                self._stage_detect_frames(job, context)
            
            elif stage.name == StageEnum.EXTRACT_TITLEBLOCK_FIELDS.value:
                self._stage_extract_fields(job, context)
            
            elif stage.name == StageEnum.A4_MULTIPAGE_GROUPING.value:
                self._stage_a4_grouping(job, context)
            
            elif stage.name == StageEnum.SPLIT_AND_RENAME.value:
                self._stage_split(job, context)
            
            elif stage.name == StageEnum.EXPORT_PDF_AND_DWG.value:
                self._stage_export(job, context)
            
            elif stage.name == StageEnum.GENERATE_DOCS.value:
                self._stage_generate_docs(job, context)
            
            elif stage.name == StageEnum.PACKAGE_ZIP.value:
                self._stage_package(job, context)
            
            # 其他阶段暂时跳过
            
        except Exception as e:
            logger.error(f"[{job.job_id}] 阶段失败 {stage.name}: {e}")
            job.add_flag(f"阶段失败:{stage.name}")
            # 根据策略决定是否继续
            raise
        
        job.progress.percent = stage.progress_end
    
    def _stage_ingest(self, job: Job, context: dict) -> None:
        """落盘与校验"""
        input_dir = job.work_dir / "input"
        input_dir.mkdir(exist_ok=True)
        
        # 复制输入文件到工作目录
        for f in job.input_files:
            if f.exists():
                import shutil
                shutil.copy(f, input_dir / f.name)
    
    def _stage_convert(self, job: Job, context: dict) -> None:
        """DWG转DXF"""
        input_dir = job.work_dir / "input"
        dxf_dir = job.work_dir / "work" / "dxf"
        dxf_dir.mkdir(parents=True, exist_ok=True)
        
        for dwg_file in input_dir.glob("*.dwg"):
            try:
                dxf_path = self.oda.dwg_to_dxf(dwg_file, dxf_dir)
                context["dxf_files"].append(dxf_path)
            except Exception as e:
                logger.warning(f"DWG转换失败: {dwg_file}: {e}")
                job.add_flag(f"转换失败:{dwg_file.name}")
    
    def _stage_detect_frames(self, job: Job, context: dict) -> None:
        """图框检测"""
        for dxf_path in context["dxf_files"]:
            try:
                frames = self.frame_detector.detect_frames(dxf_path)
                context["frames"].extend(frames)
            except Exception as e:
                logger.warning(f"图框检测失败: {dxf_path}: {e}")
                job.add_flag(f"检测失败:{dxf_path.name}")
    
    def _stage_extract_fields(self, job: Job, context: dict) -> None:
        """字段提取"""
        for i, frame in enumerate(context["frames"]):
            dxf_path = frame.runtime.source_file
            try:
                self.titleblock_extractor.extract_fields(dxf_path, frame)
            except Exception as e:
                logger.warning(f"字段提取失败: {frame.frame_id}: {e}")
                frame.add_flag(f"提取失败")
    
    def _stage_a4_grouping(self, job: Job, context: dict) -> None:
        """A4多页成组"""
        remaining, sheet_sets = self.a4_grouper.group_a4_pages(context["frames"])
        context["frames"] = remaining
        context["sheet_sets"] = sheet_sets
    
    def _stage_split(self, job: Job, context: dict) -> None:
        """裁切拆分"""
        drawings_dir = job.work_dir / "output" / "drawings"
        drawings_dir.mkdir(parents=True, exist_ok=True)
        
        # 普通图框
        for frame in context["frames"]:
            try:
                self.splitter.split_frame(
                    frame.runtime.source_file, frame, drawings_dir
                )
            except Exception as e:
                logger.warning(f"拆分失败: {frame.frame_id}: {e}")
                frame.add_flag("拆分失败")
        
        # A4成组
        for sheet_set in context["sheet_sets"]:
            try:
                dxf_path = sheet_set.master_page.frame_meta.runtime.source_file
                self.splitter.split_sheet_set(dxf_path, sheet_set, drawings_dir)
            except Exception as e:
                logger.warning(f"A4成组拆分失败: {sheet_set.cluster_id}: {e}")
                sheet_set.flags.append("拆分失败")
    
    def _stage_export(self, job: Job, context: dict) -> None:
        """导出PDF和DWG"""
        # 在split阶段已完成
        pass
    
    def _stage_generate_docs(self, job: Job, context: dict) -> None:
        """生成文档"""
        docs_dir = job.work_dir / "output" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        ied_dir = job.work_dir / "ied"
        ied_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建DocContext
        doc_ctx = self._build_doc_context(job, context)
        
        # 计算派生字段
        doc_ctx.derived = self.derivation.compute(doc_ctx)
        
        # 生成封面
        try:
            cover_docx, cover_pdf = self.cover_gen.generate(doc_ctx, docs_dir)
        except Exception as e:
            logger.error(f"封面生成失败: {e}")
            job.add_flag("封面生成失败")
        
        # 生成目录
        try:
            catalog_xlsx, catalog_pdf, page_count = self.catalog_gen.generate(doc_ctx, docs_dir)
            doc_ctx.derived.catalog_page_total = page_count
        except Exception as e:
            logger.error(f"目录生成失败: {e}")
            job.add_flag("目录生成失败")
        
        # 生成设计文件
        try:
            self.design_gen.generate(doc_ctx, docs_dir)
        except Exception as e:
            logger.error(f"设计文件生成失败: {e}")
            job.add_flag("设计文件生成失败")
        
        # 生成IED（单独输出）
        try:
            ied_xlsx = self.ied_gen.generate(doc_ctx, ied_dir)
            job.artifacts.ied_xlsx = ied_xlsx
        except Exception as e:
            logger.error(f"IED生成失败: {e}")
            job.add_flag("IED生成失败")
        
        job.artifacts.docs_dir = docs_dir
    
    def _build_doc_context(self, job: Job, context: dict) -> DocContext:
        """构建文档生成上下文"""
        params = GlobalDocParams(
            project_no=job.project_no,
            **job.params,
        )
        
        return DocContext(
            params=params,
            frames=context["frames"],
            sheet_sets=context["sheet_sets"],
            rules=self.spec.doc_generation.get("rules", {}),
            mappings=self.spec.get_mappings(),
            options=job.options,
        )
    
    def _stage_package(self, job: Job, context: dict) -> None:
        """打包"""
        zip_path = self.packager.package(job)
        manifest_path = self.packager.generate_manifest(job)
        
        job.artifacts.package_zip = zip_path
        job.artifacts.drawings_dir = job.work_dir / "output" / "drawings"
