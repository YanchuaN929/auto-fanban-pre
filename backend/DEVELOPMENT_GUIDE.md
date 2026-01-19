# 开发指南 - 逐模块开发与测试规范

## 核心原则

**每完成一段代码任务，必须运行 pytest 验证**

```bash
# 通用命令格式
pytest tests/unit/test_<module>.py -v

# 示例
pytest tests/unit/test_models.py -v
pytest tests/unit/test_config.py -v
pytest tests/unit/test_derivation.py -v
```

## 模块开发模板

### 1. 创建新模块时

```python
"""
<模块名> - <简要描述>

职责：
1. ...
2. ...

依赖：
- <依赖的库或模块>

测试要点：
- test_xxx: <测试说明>
- test_yyy: <测试说明>
"""

from __future__ import annotations

from ..interfaces import I<Interface>  # 实现接口


class <ClassName>(I<Interface>):
    """<类描述>"""
    
    def __init__(self, ...):
        ...
```

### 2. 创建测试文件时

```python
"""
<模块名>单元测试

每个模块完成后必须运行：pytest tests/unit/test_<module>.py -v
"""

import pytest

from src.<module> import <Class>


class Test<Class>:
    """<类>测试"""
    
    @pytest.fixture
    def instance(self) -> <Class>:
        return <Class>()
    
    def test_<method>_<scenario>(self, instance: <Class>):
        """测试<方法>-<场景>"""
        # Arrange
        ...
        # Act
        result = instance.<method>(...)
        # Assert
        assert result == expected
```

## 各模块测试检查清单

### 模块1：配置层 (config/)

```bash
pytest tests/unit/test_config.py -v
```

✅ 检查项：
- [ ] SpecLoader.load() 正常加载YAML
- [ ] get_paper_variants() 返回正确的图幅配置
- [ ] get_roi_profile() 返回正确的ROI配置
- [ ] get_cover_bindings() 区分1818和通用
- [ ] RuntimeConfig 加载默认值正确

### 模块2：CAD处理 (cad/)

```bash
pytest tests/unit/test_oda_converter.py -v
pytest tests/unit/test_frame_detector.py -v
```

✅ 检查项：
- [ ] ODAConverter.dwg_to_dxf() 调用正确
- [ ] ODAConverter 超时处理
- [ ] FrameDetector.detect_frames() 找到候选矩形
- [ ] 纸张尺寸拟合正确（2%容差）
- [ ] 锚点验证逻辑

### 模块3：图签提取 (cad/titleblock_extractor.py)

```bash
pytest tests/unit/test_titleblock_extractor.py -v
```

✅ 检查项：
- [ ] ROI坐标还原公式正确
- [ ] internal_code 解析（两种格式）
- [ ] external_code 解析（19位）
- [ ] 中英文标题分流（y聚类）
- [ ] page_info 解析（共N张第M张）
- [ ] revision/status/date 取列内最高y

### 模块4：A4多页成组 (cad/a4_multipage.py)

```bash
pytest tests/unit/test_a4_multipage.py -v
```

✅ 检查项：
- [ ] A4图框识别
- [ ] 簇构建（间距阈值）
- [ ] Master/Slave识别
- [ ] 一致性校验（flags不中断）
- [ ] 页码提取

### 模块5：裁切拆分 (cad/splitter.py)

```bash
pytest tests/unit/test_splitter.py -v
```

✅ 检查项：
- [ ] clip_bbox计算（边距）
- [ ] 实体保留规则（bbox相交）
- [ ] 坐标不归零
- [ ] A4成组裁切

### 模块6：文档生成 (doc_gen/)

```bash
pytest tests/unit/test_derivation.py -v
pytest tests/unit/test_cover.py -v
pytest tests/unit/test_catalog.py -v
pytest tests/unit/test_design.py -v
pytest tests/unit/test_ied.py -v
```

✅ 检查项：
- [ ] 派生字段计算正确
- [ ] 封面落点区分1818/通用
- [ ] 目录行顺序（封面→目录→图纸）
- [ ] 目录页数计算与回填
- [ ] 1818目录名称列中英文换行
- [ ] IED仅Excel输出

### 模块7：流水线 (pipeline/)

```bash
pytest tests/unit/test_pipeline.py -v
```

✅ 检查项：
- [ ] 任务创建与状态管理
- [ ] 流水线阶段执行
- [ ] 进度更新
- [ ] 失败隔离
- [ ] manifest生成
- [ ] ZIP打包

## 集成测试

集成测试需要真实的DXF文件和Office环境：

```bash
# 运行集成测试（需要 dxf/ 目录下有测试文件）
pytest tests/integration/ -v -m integration

# 运行慢速测试（ODA转换、Office导出等）
pytest tests/ -v -m slow
```

## 持续集成检查

每次提交前：

```bash
# 1. 格式检查
ruff check src/

# 2. 类型检查
mypy src/

# 3. 单元测试
pytest tests/unit/ -v

# 4. 覆盖率
pytest tests/unit/ --cov=src --cov-report=term-missing
```

## 常见问题

### Q: 测试找不到模块？

```bash
# 确保安装了开发依赖
pip install -e ".[dev]"
```

### Q: 配置文件找不到？

测试时会使用 mock 规范，无需真实文件。如需测试真实加载：

```python
@pytest.mark.integration
def test_load_real_spec():
    spec = SpecLoader.load("../../documents/参数规范.yaml")
    assert spec.schema_version == "2.0"
```

### Q: Office COM 失败？

Windows 环境需要安装 Office 2016+：

```python
# 测试时可以跳过 COM 相关测试
@pytest.mark.skipif(not HAS_PYWIN32, reason="pywin32 not available")
def test_export_via_com():
    ...
```

## 下一步

1. 阅读 `documents/计划.md` 了解整体开发计划
2. 阅读 `documents/参数规范.yaml` 了解业务规则
3. 从模块1开始逐步实现，每完成一个模块运行对应测试
4. 遇到问题时参考 `documents/主体架构.md`
