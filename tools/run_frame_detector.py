import argparse
import sys
from pathlib import Path


def _add_backend_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    backend_root = repo_root / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


def _collect_inputs(dwg_dir: Path, dxf_dir: Path | None) -> list[Path]:
    if dxf_dir:
        return sorted(dxf_dir.glob("*.dxf"))
    return sorted(dwg_dir.glob("*.dwg"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run frame detector on DWG/DXF samples."
    )
    parser.add_argument(
        "--dwg-dir",
        default="test/dwg",
        help="DWG目录（默认：test/dwg）",
    )
    parser.add_argument(
        "--dxf-dir",
        default="",
        help="可选：直接使用DXF目录（绕过ODA）",
    )
    parser.add_argument(
        "--out-dir",
        default="test/dwg/_dxf_out",
        help="DWG->DXF输出目录（默认：test/dwg/_dxf_out）",
    )
    args = parser.parse_args()

    _add_backend_to_path()
    from src.cad import FrameDetector, ODAConverter  # type: ignore

    dwg_dir = Path(args.dwg_dir)
    dxf_dir = Path(args.dxf_dir) if args.dxf_dir else None
    out_dir = Path(args.out_dir)

    detector = FrameDetector()
    oda = ODAConverter()

    inputs = _collect_inputs(dwg_dir, dxf_dir)
    if not inputs:
        print("未找到可处理文件")
        return 1

    for path in inputs:
        try:
            if path.suffix.lower() == ".dwg":
                dxf_path = oda.dwg_to_dxf(path, out_dir)
            else:
                dxf_path = path
            frames = detector.detect_frames(dxf_path)
            variants = [f.runtime.paper_variant_id for f in frames]
            print(f"{path.name}: frames={len(frames)} variants={variants}")
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name}: ERROR {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
