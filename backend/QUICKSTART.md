# 快速开始 - VS Code/Cursor 环境配置

## ✅ 问题已解决

pytest 导入错误的原因是 IDE 使用了**全局 Python 解释器**而不是**虚拟环境中的 Python**。

## 🔧 解决方案

### 方案1：重新加载窗口（推荐）

1. 按 `Ctrl+Shift+P`
2. 输入 "Developer: Reload Window"
3. IDE 会自动检测 `.vscode/settings.json` 并使用虚拟环境

### 方案2：手动选择 Python 解释器

1. 按 `Ctrl+Shift+P`
2. 输入 "Python: Select Interpreter"
3. 选择：
   ```
   Python 3.13.3 ('venv': venv) .\backend\.venv\Scripts\python.exe
   ```

### 方案3：验证当前解释器

在 VS Code 左下角查看，应显示：
```
Python 3.13.3 ('venv': venv)
```

## ✅ 验证环境

在 VS Code 终端中运行：

```powershell
# 确保虚拟环境已激活（提示符前有 (.venv)）
cd backend
.\.venv\Scripts\Activate.ps1

# 验证 Python 路径
python -c "import sys; print(sys.executable)"
# 应输出: D:\Programs\auto-fanban\auto-fanban-pre\backend\.venv\Scripts\python.exe

# 验证 pytest
pytest --version
# 应输出: pytest 9.0.2

# 运行测试
pytest tests/unit/ -v
```

## 📁 已创建的配置文件

### `.vscode/settings.json`
- ✅ 指定虚拟环境路径
- ✅ 启用 pytest 测试框架
- ✅ 配置 Ruff 代码检查和格式化
- ✅ 添加 `src` 到分析路径（解决导入错误）

### `.vscode/extensions.json`
- ✅ 推荐安装 Python 扩展
- ✅ 推荐安装 Pylance（类型检查）
- ✅ 推荐安装 Ruff（代码质量）

## 🎯 测试环境

### 运行测试

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行特定测试文件
pytest tests/unit/test_models.py -v

# 运行带覆盖率报告
pytest tests/unit/ --cov=src --cov-report=term-missing
```

### 当前测试状态

- ✅ 21 个测试通过
- ⚠️ 7 个测试需要真实配置文件（可忽略）

## 🚀 开始开发

现在您可以：

1. ✅ 导入不再报错
2. ✅ 代码补全正常工作
3. ✅ 类型检查已启用
4. ✅ 测试框架已配置
5. ✅ 代码格式化已设置

### 开发流程

```bash
# 1. 激活虚拟环境
cd backend
.\.venv\Scripts\Activate.ps1

# 2. 开发代码
# 在 src/ 目录下编写代码

# 3. 运行测试
pytest tests/unit/test_xxx.py -v

# 4. 代码检查
ruff check src/

# 5. 类型检查
mypy src/
```

## 📚 下一步

按照 `backend/DEVELOPMENT_GUIDE.md` 中的模块开发顺序开始实现功能！
