# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

CNPE 图纸处理系统 (auto-fanban) — A Python backend for batch processing of DWG/DXF engineering drawings for Chinese nuclear power projects. It handles CAD processing (frame detection, titleblock extraction) and document generation (cover pages, table of contents, design file registers, IED plans). The FastAPI API layer is **not yet implemented** (planned as module 7).

### Python version

The project requires **Python ≥ 3.13**. The VM's default `python3` is 3.12, so the venv is created with `python3.13` (installed from the deadsnakes PPA). Always use the venv at `backend/.venv`.

### Running commands

**Critical**: All commands (pytest, ruff, mypy, python scripts) must be run from the **repository root** (`/workspace`), not from `/workspace/backend`. The code loads YAML specs via relative paths like `documents/参数规范.yaml`, which resolve from the CWD.

### Activating the virtual environment

```bash
source /workspace/backend/.venv/bin/activate
```

### Lint / Type-check / Test

See `backend/README.md` for full details. Key commands (run from `/workspace`):

```bash
# Lint
ruff check backend/src/
ruff check backend/tests/

# Type check (59 pre-existing errors in codebase)
mypy backend/src/

# Unit tests (116 tests, all pass)
pytest backend/tests/unit/ -v
```

### Running the application

There is no runnable web server yet (FastAPI API layer is module 7, not yet implemented). The core functionality is exercised through unit tests and the tools in `tools/`.

### Windows-only features

PDF export via Office COM (`pywin32`) and DWG→DXF conversion via ODA File Converter are **Windows-only**. On Linux, these features are unavailable, but all unit tests still pass because they mock the COM interfaces. The `pywin32` dependency is conditional (`sys_platform == 'win32'`) and is not installed on Linux.
