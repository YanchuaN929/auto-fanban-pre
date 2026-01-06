import json
import os
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_dxf_roi_extract import load_spec, get_titleblock_spec, Rect, rect_from_rb_offset, iter_text_items_in_space

# Avoid hardcoding non-ASCII filename in source: pick the only yaml under documents
yamls = [p for p in os.listdir("documents") if p.lower().endswith(".yaml") and ".bak" not in p.lower()]
if len(yamls) != 1:
    raise SystemExit(f"expected exactly 1 yaml under documents, got: {yamls}")
spec = load_spec(Path("documents") / yamls[0])

tb = get_titleblock_spec(spec)
rep = json.load(open("documents/dxf_roi_test_report_A0_summary.json", encoding="utf-8"))
outer0 = rep["best_candidate"]["outer"]
outer = Rect(outer0["xmin"], outer0["ymin"], outer0["xmax"], outer0["ymax"])
sx = rep["best_candidate"]["sx"]
sy = rep["best_candidate"]["sy"]
prof_id = rep["best_candidate"]["roi_profile_id_default"]
profile = tb["roi_profiles"][prof_id]
rb = profile["fields_rb_offset_1to1"]
roi_map = tb.get("roi_field_name_mapping", {})

keys = {"revision": roi_map.get("revision"), "date": roi_map.get("date"), "status": roi_map.get("status")}
rois = {k: rect_from_rb_offset(outer=outer, rb_offset=[float(x) for x in rb[v]], sx=sx, sy=sy) for k, v in keys.items()}

doc = ezdxf.readfile("dxf/A0.dxf")
items = list(iter_text_items_in_space(doc.modelspace()))

for k, roi in rois.items():
    hits = [it for it in items if (roi.xmin <= it.x < roi.xmax and roi.ymin <= it.y < roi.ymax)]
    hits.sort(key=lambda it: (-it.y, it.x))
    print("\n===", k, "roi_name=", keys[k], "hit_count=", len(hits))
    for it in hits[:50]:
        t = (it.text or "").replace("\n", "\\n")
        print("  (%0.3f,%0.3f) %s text=%r" % (it.x, it.y, it.src, t))
