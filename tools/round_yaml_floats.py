import argparse
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def _round_str(num_str: str, decimals: int, *, fixed_decimals: bool) -> str:
    """
    Round a decimal string to given decimals, then trim trailing zeros.
    Keeps at most `decimals` digits after the decimal point.
    """
    q = Decimal("1").scaleb(-decimals)  # 10^-decimals
    d = Decimal(num_str).quantize(q, rounding=ROUND_HALF_UP)
    out = format(d, "f")
    if fixed_decimals:
        # Ensure exactly `decimals` digits after the decimal point.
        if "." not in out:
            return out + "." + ("0" * decimals)
        int_part, frac_part = out.split(".", 1)
        frac_part = (frac_part + ("0" * decimals))[:decimals]
        return f"{int_part}.{frac_part}"
    else:
        if "." in out:
            out = out.rstrip("0").rstrip(".")
        return out


def _should_format_number(path_keys: list[str], key: str | None) -> bool:
    """
    Only format numbers in calibration-related blocks:
    - sections.titleblock_extraction_spec.scale_fit.canonical_variants.*.(W|H)
    - sections.titleblock_extraction_spec.roi_profiles.*.fields_rb_offset_1to1.*.[list items]
    - sections.titleblock_extraction_spec.(tolerance|scale_fit.fit_method|roi_profiles.*.tolerance_abs)
    """
    path = "/".join(path_keys)
    if "sections/titleblock_extraction_spec/scale_fit/canonical_variants" in path:
        return key in {"W", "H"}
    if "sections/titleblock_extraction_spec/roi_profiles" in path:
        if "fields_rb_offset_1to1" in path:
            return True  # list items
        return key in {"tolerance_abs"}
    if "sections/titleblock_extraction_spec/tolerance" in path:
        return True
    if "sections/titleblock_extraction_spec/scale_fit/fit_method" in path:
        return True
    return False


def round_yaml_floats(text: str, decimals: int, *, fixed_decimals: bool) -> tuple[str, int]:
    """
    Format calibration numbers to given decimals within targeted sections.
    This is indentation-aware (lightweight), so we don't accidentally rewrite unrelated ints like pipeline step numbers.
    """
    key_only_re = re.compile(r"^(\s*)([^:#]+):\s*$")
    key_value_num_re = re.compile(r"^(\s*)([^:#]+):\s*(-?\d+(?:\.\d+)?)\s*$")
    list_num_re = re.compile(r"^(\s*)-\s*(-?\d+(?:\.\d+)?)\s*$")

    stack: list[tuple[int, str]] = []  # (indent, key)

    out_lines: list[str] = []
    count = 0

    for line in text.splitlines(keepends=False):
        m = key_only_re.match(line)
        if m:
            indent = len(m.group(1))
            key = m.group(2).strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, key))
            out_lines.append(line)
            continue

        m = key_value_num_re.match(line)
        if m:
            indent = len(m.group(1))
            key = m.group(2).strip()
            num = m.group(3)
            while stack and stack[-1][0] >= indent:
                stack.pop()
            path_keys = [k for _, k in stack] + [key]
            if _should_format_number(path_keys, key):
                new_num = _round_str(num, decimals, fixed_decimals=fixed_decimals)
                if new_num != num:
                    count += 1
                out_lines.append(f"{m.group(1)}{m.group(2)}: {new_num}")
            else:
                out_lines.append(line)
            continue

        m = list_num_re.match(line)
        if m:
            indent = len(m.group(1))
            num = m.group(2)
            # list items belong to current stack context (do not push/pop)
            path_keys = [k for _, k in stack]
            if _should_format_number(path_keys, None):
                new_num = _round_str(num, decimals, fixed_decimals=fixed_decimals)
                if new_num != num:
                    count += 1
                out_lines.append(f"{m.group(1)}- {new_num}")
            else:
                out_lines.append(line)
            continue

        out_lines.append(line)

    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), count


def main() -> int:
    ap = argparse.ArgumentParser(description="Round high-precision float literals in a YAML text file.")
    ap.add_argument(
        "path",
        help="YAML file path OR a directory containing 参数规范.yaml (useful on Windows terminals where non-ASCII args may garble)",
    )
    ap.add_argument("--decimals", type=int, default=3, help="Max decimals to keep (default: 3)")
    ap.add_argument(
        "--fixed-decimals",
        action="store_true",
        help="Always write exactly N decimals (e.g. 1189.000) instead of trimming zeros",
    )
    ap.add_argument("--backup", action="store_true", help="Write <path>.bak before modifying")
    args = ap.parse_args()

    path = Path(args.path)
    if path.is_dir():
        # Prefer exact filename to avoid passing non-ASCII via CLI.
        candidate = path / "参数规范.yaml"
        if candidate.exists():
            path = candidate
        else:
            # Fallback: pick the first YAML that ends with that name (in case of different directory layouts).
            matches = [p for p in path.glob("*.yaml") if p.name.endswith("参数规范.yaml")]
            if not matches:
                raise SystemExit(f"Could not find 参数规范.yaml under directory: {path}")
            path = matches[0]

    raw = path.read_text(encoding="utf-8")
    new, count = round_yaml_floats(raw, args.decimals, fixed_decimals=args.fixed_decimals)

    if args.backup:
        bak = path.with_suffix(path.suffix + ".bak")
        if bak.exists():
            bak = path.with_suffix(path.suffix + ".bak2")
        bak.write_text(raw, encoding="utf-8")
    path.write_text(new, encoding="utf-8")

    print(f"rounded_matches={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


