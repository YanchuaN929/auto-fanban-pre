# CNPE 图纸处理系统 - 后端

## 环境要求

- **Python**: 3.13.3+
- **操作系统**: Windows 10/11（需要 Office COM 自动化）
- **外部依赖**: ODA File Converter、Microsoft Office 2016+

## 快速开始

### 方式1：使用搭建脚本（推荐）

```powershell
# PowerShell
cd backend
.\setup_env.ps1
```

```cmd
# CMD
cd backend
setup_env.bat
```

### 方式2：手动搭建

```powershell
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活环境
.venv\Scripts\Activate.ps1  # PowerShell
# 或
.venv\Scripts\activate.bat  # CMD

# 3. 升级 pip
python -m pip install --upgrade pip setuptools wheel

# 4. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install pywin32>=308  # Windows COM

# 5. 开发模式安装
pip install -e .
```

### 验证安装

```powershell
# 检查 Python 版本
python --version  # 应显示 Python 3.13.x

# 运行单元测试
pytest tests/unit/ -v
```

## 目录结构

```
backend/
├── src/                    # 源代码
│   ├── __init__.py
│   ├── interfaces.py       # 模块接口契约
│   ├── config/             # 配置层
│   │   ├── __init__.py
│   │   ├── spec_loader.py  # 业务规范加载器
│   │   └── runtime_config.py # 运行期配置
│   ├── models/             # 数据模型
│   │   ├── __init__.py
│   │   ├── job.py          # 任务模型
│   │   ├── frame.py        # 图框模型
│   │   ├── sheet_set.py    # A4多页成组
│   │   └── doc_context.py  # 文档生成上下文
│   ├── cad/                # CAD处理模块
│   │   ├── __init__.py
│   │   ├── oda_converter.py      # DWG↔DXF转换
│   │   ├── frame_detector.py     # 图框检测
│   │   ├── titleblock_extractor.py # 图签提取
│   │   ├── a4_multipage.py       # A4多页成组
│   │   └── splitter.py           # 裁切拆分
│   ├── doc_gen/            # 文档生成模块
│   │   ├── __init__.py
│   │   ├── derivation.py   # 派生字段计算
│   │   ├── cover.py        # 封面生成
│   │   ├── catalog.py      # 目录生成
│   │   ├── design.py       # 设计文件生成
│   │   ├── ied.py          # IED计划生成
│   │   └── pdf_engine.py   # PDF导出引擎
│   └── pipeline/           # 流水线模块
│       ├── __init__.py
│       ├── stages.py       # 阶段定义
│       ├── executor.py     # 流水线执行器
│       ├── job_manager.py  # 任务管理
│       └── packager.py     # 打包与manifest
├── tests/                  # 测试
│   ├── __init__.py
│   ├── conftest.py         # 公共fixtures
│   └── unit/               # 单元测试
│       ├── __init__.py
│       ├── test_models.py
│       ├── test_config.py
│       └── test_derivation.py
├── pyproject.toml          # 项目配置
└── README.md               # 本文件
```

## 设计原则

### 1. 高度解耦

- **接口契约**：所有模块通过 `interfaces.py` 定义的抽象接口通信
- **依赖注入**：模块通过构造函数接收依赖，便于测试和替换
- **数据模型**：模块间通过 `models/` 中定义的数据结构交换信息

### 2. 单一职责

每个文件只做一件事：
- `oda_converter.py`：只负责 DWG↔DXF 转换
- `frame_detector.py`：只负责图框检测
- `derivation.py`：只负责派生字段计算

### 3. 配置驱动

- **业务规范**：`documents/参数规范.yaml` 是唯一权威源
- **运行期配置**：`documents/参数规范_运行期.yaml`
- **无硬编码**：ROI坐标、模板落点、映射表全部从YAML读取

## 开发流程

### 1. 环境准备

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev]"
```

### 2. 开发单个模块

每完成一段代码后，必须运行对应的单元测试：

```bash
# 示例：完成 frame_detector.py 后
pytest tests/unit/test_frame_detector.py -v

# 运行所有单元测试
pytest tests/unit/ -v

# 只运行快速单元测试（排除集成测试）
pytest tests/unit/ -v -m "not slow"
```

### 3. 测试规范

每个模块的测试文件头部会列出必须覆盖的测试点，例如：

```python
"""
图框检测器单元测试

测试要点：
- test_detect_single_frame: 单图框检测
- test_detect_multiple_frames: 多图框检测
- test_paper_fitting: 纸张尺寸拟合
- test_anchor_verification: 锚点验证
"""
```

### 4. 代码风格

```bash
# 格式检查
ruff check src/

# 类型检查
mypy src/
```

## 模块开发顺序

按 `documents/计划.md` 推荐顺序：

1. **模块1：框架与配置层** ✅
   - `config/spec_loader.py`
   - `config/runtime_config.py`
   - 测试：`pytest tests/unit/test_config.py -v`

2. **模块2：DWG→DXF 与图框检测**
   - `cad/oda_converter.py`
   - `cad/frame_detector.py`
   - 测试：`pytest tests/unit/test_cad.py -v`

3. **模块3：图签字段提取**
   - `cad/titleblock_extractor.py`
   - 测试：`pytest tests/unit/test_titleblock.py -v`

4. **模块4：A4多页成组**
   - `cad/a4_multipage.py`
   - 测试：`pytest tests/unit/test_a4_multipage.py -v`

5. **模块5：裁切/拆分与输出**
   - `cad/splitter.py`
   - 测试：`pytest tests/unit/test_splitter.py -v`

6. **模块6：文档生成**
   - `doc_gen/derivation.py` ✅
   - `doc_gen/cover.py`
   - `doc_gen/catalog.py`
   - `doc_gen/design.py`
   - `doc_gen/ied.py`
   - 测试：`pytest tests/unit/test_doc_gen.py -v`

7. **模块7：打包与API**
   - `pipeline/packager.py`
   - `api/` (FastAPI)
   - 测试：`pytest tests/unit/test_pipeline.py -v`

## 数据流

```
DWG文件
    ↓
[ODAConverter] DWG→DXF
    ↓
[FrameDetector] 图框检测 → FrameMeta.runtime
    ↓
[TitleblockExtractor] 字段提取 → FrameMeta.titleblock
    ↓
[A4MultipageGrouper] A4成组 → SheetSet
    ↓
[DerivationEngine] 派生计算 → DerivedFields
    ↓
[DocContext] 聚合所有数据
    ↓
[CoverGenerator/CatalogGenerator/...] 文档生成
    ↓
[Packager] 打包 → package.zip + manifest.json
```

## 关键约定

### 1. 失败隔离

- 单图框处理失败不影响全局
- 错误记录到 `job.flags` 或 `job.errors`
- 一致性问题（比例不一致、页数不一致等）只打 flags，不中断

### 2. 坐标系

- ROI 使用 `rb_offset_scaled` 坐标系（相对右下角）
- 裁切时保持原始坐标，不归零

### 3. PDF 输出

- 封面/目录/设计文件必须导出 PDF
- IED 仅 Excel，单独输出，不入 package.zip
- PDF 引擎优先 Office COM，兜底 LibreOffice

### 4. 目录页数

- 优先使用 Excel 分页信息计页
- 兜底：导出PDF计页 → 回填 → 再导出
