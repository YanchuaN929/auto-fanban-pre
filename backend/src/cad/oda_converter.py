"""
ODA 转换器 - DWG↔DXF 转换

职责：
- 调用 ODA File Converter 执行格式转换
- 处理超时和错误
- 清理临时文件

依赖：
- ODA File Converter 可执行文件（路径由运行期配置指定）

测试要点：
- test_dwg_to_dxf_success: 正常转换
- test_dwg_to_dxf_timeout: 超时处理
- test_dwg_to_dxf_file_not_found: 文件不存在
- test_dxf_to_dwg_success: 反向转换
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import get_config
from ..interfaces import ConversionError, IODAConverter


class ODAConverter(IODAConverter):
    """ODA File Converter 封装"""
    
    def __init__(self, exe_path: str | None = None, timeout: int | None = None):
        config = get_config()
        self.exe_path = Path(exe_path or config.oda.exe_path)
        self.timeout = timeout or config.timeouts.oda_convert_sec
    
    def dwg_to_dxf(self, dwg_path: Path, output_dir: Path) -> Path:
        """DWG 转 DXF"""
        if not dwg_path.exists():
            raise ConversionError(f"DWG文件不存在: {dwg_path}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{dwg_path.stem}.dxf"
        
        # TODO: 实现ODA调用
        # 示例命令: ODAFileConverter.exe <input_dir> <output_dir> ACAD2018 DXF
        cmd = [
            str(self.exe_path),
            str(dwg_path.parent),
            str(output_dir),
            "ACAD2018",
            "DXF",
            "0",  # Recursive
            "1",  # Audit
            f"*.{dwg_path.suffix[1:]}",  # Filter
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True,
            )
        except subprocess.TimeoutExpired as e:
            raise ConversionError(f"ODA转换超时: {dwg_path}") from e
        except subprocess.CalledProcessError as e:
            raise ConversionError(f"ODA转换失败: {e.stderr}") from e
        
        if not output_path.exists():
            raise ConversionError(f"转换后文件不存在: {output_path}")
        
        return output_path
    
    def dxf_to_dwg(self, dxf_path: Path, output_dir: Path) -> Path:
        """DXF 转 DWG"""
        if not dxf_path.exists():
            raise ConversionError(f"DXF文件不存在: {dxf_path}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{dxf_path.stem}.dwg"
        
        # TODO: 实现ODA调用
        cmd = [
            str(self.exe_path),
            str(dxf_path.parent),
            str(output_dir),
            "ACAD2018",
            "DWG",
            "0",
            "1",
            f"*.dxf",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True,
            )
        except subprocess.TimeoutExpired as e:
            raise ConversionError(f"ODA转换超时: {dxf_path}") from e
        except subprocess.CalledProcessError as e:
            raise ConversionError(f"ODA转换失败: {e.stderr}") from e
        
        if not output_path.exists():
            raise ConversionError(f"转换后文件不存在: {output_path}")
        
        return output_path
