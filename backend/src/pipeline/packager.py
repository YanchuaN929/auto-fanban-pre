"""
打包器 - 生成交付包和manifest

职责：
1. 打包output目录为package.zip
2. 生成manifest.json
3. IED单独输出（不入zip）

测试要点：
- test_package_zip: ZIP打包
- test_manifest_structure: manifest结构
- test_ied_separate: IED单独输出
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import load_spec
from ..interfaces import IPackager

if TYPE_CHECKING:
    from ..models import Job


class Packager(IPackager):
    """打包器实现"""
    
    def __init__(self, spec_path: str | None = None):
        self.spec = load_spec(spec_path) if spec_path else load_spec()
    
    def package(self, job: Job) -> Path:
        """打包交付产物"""
        if not job.work_dir:
            raise ValueError("Job work_dir not set")
        
        output_dir = job.work_dir / "output"
        zip_path = job.work_dir / "package.zip"
        
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 打包drawings目录
            drawings_dir = output_dir / "drawings"
            if drawings_dir.exists():
                for file in drawings_dir.rglob("*"):
                    if file.is_file():
                        arcname = f"drawings/{file.relative_to(drawings_dir)}"
                        zf.write(file, arcname)
            
            # 打包docs目录
            docs_dir = output_dir / "docs"
            if docs_dir.exists():
                for file in docs_dir.rglob("*"):
                    if file.is_file():
                        arcname = f"docs/{file.relative_to(docs_dir)}"
                        zf.write(file, arcname)
            
            # 打包manifest
            manifest_path = job.work_dir / "manifest.json"
            if manifest_path.exists():
                zf.write(manifest_path, "manifest.json")
        
        return zip_path
    
    def generate_manifest(self, job: Job) -> Path:
        """生成manifest.json"""
        if not job.work_dir:
            raise ValueError("Job work_dir not set")
        
        manifest = {
            "schema_version": "1.0",
            "job_id": job.job_id,
            "job_type": job.job_type.value,
            "project_no": job.project_no,
            "spec_version": f"documents/参数规范.yaml@{self.spec.schema_version}",
            
            "inputs": {
                "dwg_files": [str(f.name) for f in job.input_files],
                "options": job.options,
                "params": job.params,
            },
            
            "derived": {},  # 由executor填充
            
            "artifacts": {
                "package_zip": str(job.artifacts.package_zip) if job.artifacts.package_zip else None,
                "ied_xlsx": str(job.artifacts.ied_xlsx) if job.artifacts.ied_xlsx else None,
                "drawings_dir": str(job.artifacts.drawings_dir) if job.artifacts.drawings_dir else None,
                "docs_dir": str(job.artifacts.docs_dir) if job.artifacts.docs_dir else None,
            },
            
            "flags": job.flags,
            "errors": job.errors,
            
            "timestamps": {
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            },
        }
        
        manifest_path = job.work_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        
        return manifest_path
