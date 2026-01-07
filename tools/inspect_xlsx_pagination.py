"""
检查 xlsx 的分页/打印相关配置（只读，标准库）。

用法：
  python tools/inspect_xlsx_pagination.py --xlsx documents_bin/目录模板文件.xlsx
  python tools/inspect_xlsx_pagination.py --xlsx documents_bin/1818图册目录模板.xlsx
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    t = (el.text or "").strip()
    return t or None


def inspect_xlsx(xlsx_path: Path) -> dict:
    out: dict = {"xlsx": str(xlsx_path)}
    with zipfile.ZipFile(xlsx_path, "r") as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        dn = wb.find("s:definedNames", NS)
        defined_names: list[dict] = []
        if dn is not None:
            for n in dn.findall("s:definedName", NS):
                defined_names.append({"name": n.attrib.get("name"), "value": (n.text or "").strip()})

        # sheet1 only (catalog templates use Sheet1)
        s1 = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        page_setup = s1.find("s:pageSetup", NS)
        page_margins = s1.find("s:pageMargins", NS)
        print_options = s1.find("s:printOptions", NS)
        header_footer = s1.find("s:headerFooter", NS)

        hf: dict = {}
        if header_footer is not None:
            for tag in ["oddHeader", "oddFooter", "evenHeader", "evenFooter", "firstHeader", "firstFooter"]:
                t = _text(header_footer.find(f"s:{tag}", NS))
                if t is not None:
                    hf[tag] = t

        out.update(
            {
                "sheet1": {
                    "pageSetup": (page_setup.attrib if page_setup is not None else None),
                    "pageMargins": (page_margins.attrib if page_margins is not None else None),
                    "printOptions": (print_options.attrib if print_options is not None else None),
                    "headerFooter": (hf if hf else None),
                },
                "definedNames": defined_names,
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="")
    ap.add_argument("--root", default="")
    ap.add_argument("--kind", default="", choices=["", "catalog_common", "catalog_1818"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    xlsx_path: Path | None = None
    if args.xlsx:
        xlsx_path = Path(args.xlsx)
    elif args.root and args.kind:
        root = Path(args.root)
        if not root.exists() or not root.is_dir():
            raise SystemExit(f"--root not found or not a dir: {root}")

        # Use unicode escapes to avoid terminal encoding issues.
        name_common = "\u76ee\u5f55\u6a21\u677f\u6587\u4ef6.xlsx"  # 目录模板文件.xlsx
        name_1818 = "1818\u56fe\u518c\u76ee\u5f55\u6a21\u677f.xlsx"  # 1818图册目录模板.xlsx

        candidates = [p for p in root.iterdir() if p.suffix.lower() == ".xlsx"]
        if args.kind == "catalog_common":
            for p in candidates:
                if p.name == name_common:
                    xlsx_path = p
                    break
        elif args.kind == "catalog_1818":
            for p in candidates:
                if p.name == name_1818:
                    xlsx_path = p
                    break
    else:
        raise SystemExit("Provide --xlsx PATH, or (--root DIR and --kind catalog_common/catalog_1818)")

    if xlsx_path is None:
        raise SystemExit("Could not resolve xlsx_path from args (maybe filename changed?)")

    data = inspect_xlsx(xlsx_path)
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] wrote: {args.out}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


