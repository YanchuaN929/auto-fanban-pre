"""
配置层 - 加载业务规范与运行期配置

职责：
- 加载 documents/参数规范.yaml（业务规范）
- 加载 documents/参数规范_运行期.yaml（运行期参数）
- 提供类型安全的配置访问接口
"""

from .spec_loader import SpecLoader, BusinessSpec, load_spec
from .runtime_config import RuntimeConfig, get_config, reload_config

__all__ = [
    "SpecLoader",
    "BusinessSpec",
    "load_spec",
    "RuntimeConfig",
    "get_config",
    "reload_config",
]
