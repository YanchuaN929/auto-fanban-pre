"""
PDF页数统计（标准库，适用于导出后的catalog.pdf计页）。

注意：这是一个轻量实现，依赖“/Type /Page”标记计数（排除 /Type /Pages）。
对绝大多数由 Office/LibreOffice 导出的 PDF 都足够稳定。
"""

from __future__ import annotations

import argparse
from pathlib import Path


def count_pdf_pages(path: Path) -> int:
    data = path.read_bytes()
    # Count "/Type /Page" but exclude "/Type /Pages"
    needle = b"/Type /Page"
    count = 0
    i = 0
    while True:
        j = data.find(needle, i)
        if j < 0:
            break
        # next char after "/Type /Page" distinguishes "Pages"
        k = j + len(needle)
        if k < len(data) and data[k : k + 1] == b"s":
            i = k
            continue
        count += 1
        i = k
    return count


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    args = ap.parse_args()
    n = count_pdf_pages(Path(args.pdf))
    print(n)


if __name__ == "__main__":
    main()


