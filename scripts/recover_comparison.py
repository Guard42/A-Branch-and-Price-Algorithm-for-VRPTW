"""Recover completed comparison rows from the log file."""

import json
import re
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
log = Path(r"C:\Users\Junwei Li\AppData\Local\Temp\bpvrptw-ref\bench_full_all.log")

# Match: <instance> MIP[<status>:<cost>:<time>s] BP[<status>:<cost>:<time>s] gap=<n>% match=<bool>
row_re = re.compile(
    r"(\S+\.TXT|\S+\.txt)\s+"
    r"MIP\[([\w_]+):([\d.]+):([\d.]+)s\]\s+"
    r"BP\[([\w_]+):([\d.]*):?([\d.]*)s?\]\s+"
    r"gap=(N/A|[\d.]+)%\s+match=(True|False)"
)

rows: list[dict] = []
seen: set[str] = set()
for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
    m = row_re.search(line)
    if not m:
        continue
    inst = m.group(1)
    if inst in seen:
        continue
    seen.add(inst)
    g_status = m.group(2)
    g_cost = float(m.group(3))
    g_time = float(m.group(4))
    b_status = m.group(5)
    b_cost = float(m.group(6)) if m.group(6) else None
    b_time = float(m.group(7)) if m.group(7) else 0.0
    gap_raw = m.group(8)
    match = m.group(9) == "True"

    tr = None
    if g_time > 1e-9 and b_cost is not None:
        tr = round((g_time - b_time) / g_time * 100, 2)

    rows.append({
        "instance": inst,
        "gurobi_status": g_status,
        "gurobi_cost": g_cost,
        "gurobi_time_s": g_time,
        "bp_status": b_status,
        "bp_cost": b_cost,
        "bp_time_s": b_time,
        "cost_gap_pct": float(gap_raw.replace("N/A", "0")) if gap_raw != "N/A" else None,
        "time_reduced_pct": tr,
        "cost_match": match,
    })

print(f"recovered {len(rows)} rows")
out = WS / "results" / "full_comparison.json"
out.write_text(
    json.dumps({"meta": {"recovered_from_log": True}, "rows": rows}, indent=2),
    encoding="utf-8",
)
print(f"wrote {out}")
