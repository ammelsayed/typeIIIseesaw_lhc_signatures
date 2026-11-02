#!/usr/bin/env python3
"""Build index.html: a filterable table of the decay chains with the
Feynman diagram of each row one click away.

Reads tables/decay_chains.csv, reuses the naming from
draw_feynman_diagrams.py so the image paths line up, and writes a single
self-contained index.html next to it (no CDN, works offline).

    python3 create_webpage.py
"""

import html
import os
import sys

import pandas as pd

from draw_feynman_diagrams import CSV, channel_dir, diagram_name

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")

# nL, 2L_Sign and nJ are replaced by Category.
COLS = ["Production", "Chain", "Prod. Xsec [fb]", "Br1", "Br11", "Br2", "Br22",
        "Total Cross Section [fb]", "xsec %"]
LABELS = ["Production", "Chain", "Prod. σ [fb]", "BR₁", "BR₁₁", "BR₂", "BR₂₂",
          "σ [fb]", "%"]
NUMERIC = COLS[2:]
PROD_XSEC, TOTAL_XSEC, PCT = "Prod. Xsec [fb]", "Total Cross Section [fb]", "xsec %"

PAGE = """<!DOCTYPE html>
<meta charset="utf-8">
<title>Type-III seesaw decay chains</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;color:#222}}
 h1{{font-size:18px;margin:0 0 12px}}
 table{{border-collapse:collapse;font-size:13px}}
 th,td{{border:1px solid #ccc;padding:3px 7px;text-align:left}}
 th{{background:#f0f0f0;position:sticky;top:0}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 tr.row:hover{{background:#f7f9ff}}
 tr.hide{{display:none}}
 tfoot td{{font-weight:600;background:#fafafa}}
 code{{font-family:ui-monospace,monospace;font-size:12px}}
 button{{font:inherit;padding:2px 8px;cursor:pointer}}
 select{{font:inherit;padding:3px}}
 #lb{{display:none;position:fixed;inset:0;background:#000a;z-index:9;
      align-items:center;justify-content:center}}
 #lb.on{{display:flex}}
 #lb figure{{background:#fff;margin:0;padding:10px;border-radius:6px;
      max-width:92vw;max-height:92vh;display:flex;flex-direction:column;gap:8px}}
 #lb .bar{{display:flex;gap:6px;align-items:center}}
 #lb .bar .sp{{flex:1;font:12px ui-monospace,monospace;color:#666;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
 #lb .frame{{overflow:auto;max-width:90vw;max-height:78vh;text-align:center}}
 #lb img{{transition:transform .12s;display:block;margin:auto}}
</style>

<h1>Type-III seesaw &mdash; {n} decay chains</h1>

<p>Category
 <select id="cat">
  <option value="">all ({n})</option>
  {options}
 </select>
</p>

<table>
 <thead><tr><th>Category</th>{head}<th>Diagram</th></tr></thead>
 <tbody>
{rows}
 </tbody>
 <tfoot><tr>
  <td colspan="8">Total <span id="tn"></span></td>
  <td class="num" id="tx"></td>
  <td class="num" id="tp"></td>
  <td></td>
 </tr></tfoot>
</table>

<div id="lb" onclick="if(event.target.id==='lb')close_()">
 <figure>
  <div class="bar">
   <button onclick="zoom(1.25)">+</button>
   <button onclick="zoom(0.8)">&minus;</button>
   <button onclick="reset()">reset</button>
   <span class="sp" id="lbt"></span>
   <a id="lbd" download><button>download</button></a>
   <button onclick="close_()">&times;</button>
  </div>
  <div class="frame"><img id="lbi" alt="Feynman diagram"></div>
 </figure>
</div>

<script>
const rows = [...document.querySelectorAll("tr.row")];
const sel = document.getElementById("cat");
const img = document.getElementById("lbi");
let scale = 1;

function apply() {{
  const v = sel.value;
  let n = 0, s = 0, p = 0;
  for (const r of rows) {{
    const on = !v || r.dataset.cat === v;
    r.classList.toggle("hide", !on);
    if (on) {{ n++; s += +r.dataset.xsec; p += +r.dataset.pct; }}
  }}
  document.getElementById("tn").textContent = "(" + n + ")";
  document.getElementById("tx").textContent = s.toFixed(4);
  document.getElementById("tp").textContent = p.toFixed(2) + "%";
}}
sel.onchange = apply;

function zoom(f) {{ scale *= f; img.style.transform = "scale(" + scale + ")"; }}
function reset() {{ scale = 1; img.style.transform = ""; }}
function close_() {{ document.getElementById("lb").classList.remove("on"); }}

for (const r of rows) {{
  const b = r.querySelector("button");
  b.onclick = () => {{
    img.src = b.dataset.src;
    document.getElementById("lbd").href = b.dataset.src;
    document.getElementById("lbt").textContent = b.dataset.name;
    reset();
    document.getElementById("lb").classList.add("on");
  }};
}}
addEventListener("keydown", e => {{ if (e.key === "Escape") close_(); }});
apply();
</script>
"""


def fmt(x):
    return "" if pd.isna(x) else f"{x:.4g}"


def main(csv_path=CSV):
    df = pd.read_csv(csv_path)
    df["Category"] = [channel_dir(r.nL, r._3, r.nJ) for r in df.itertuples(index=False)]

    # largest cross section first, so the dominant channels sit at the top
    df = df.sort_values(TOTAL_XSEC, ascending=False, kind="stable")
    order = sorted(df["Category"].unique(),
                   key=lambda c: (int(c.split("L")[0].rstrip("OS")), c))

    rows, missing = [], 0
    for row in df.itertuples(index=False):
        cat = row.Category
        name = diagram_name(row.Chain)
        png = f"feynman_diagrams/{cat}/{name}.png"
        if not os.path.exists(os.path.join(HERE, png)):
            missing += 1
        tds = [f"<td>{html.escape(cat)}</td>"]
        for col in COLS:
            v = row[df.columns.get_loc(col)]
            if col in ("Production", "Chain"):
                tds.append(f"<td><code>{html.escape(str(v))}</code></td>")
            else:
                tds.append(f'<td class="num">{fmt(v)}</td>')
        tds.append(f'<td><button data-src="{html.escape(png)}" '
                   f'data-name="{html.escape(name)}">diagram</button></td>')
        rows.append(
            f'<tr class="row" data-cat="{html.escape(cat)}" '
            f'data-xsec="{row[df.columns.get_loc(TOTAL_XSEC)]}" '
            f'data-pct="{row[df.columns.get_loc(PCT)]}">{"".join(tds)}</tr>')

    options = "\n  ".join(
        f'<option value="{html.escape(c)}">{html.escape(c)} ({int((df.Category == c).sum())})</option>'
        for c in order)

    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(PAGE.format(n=len(df), options=options,
                            head="".join(f"<th>{html.escape(l)}</th>" for l in LABELS),
                            rows="\n".join(rows)))
    print(f"{len(df)} rows, {len(order)} categories -> {INDEX}"
          + (f" ({missing} missing PNGs)" if missing else ""))


def _selfcheck(csv_path=CSV):
    """Check the page's totals against pandas: python3 create_webpage.py --check"""
    import re
    df = pd.read_csv(csv_path)
    df["Category"] = [channel_dir(r.nL, r._3, r.nJ) for r in df.itertuples(index=False)]
    src = open(INDEX, encoding="utf-8").read()
    rows = re.findall(r'data-cat="([^"]+)" data-xsec="([^"]+)" data-pct="([^"]+)"', src)
    assert len(rows) == len(df), f"{len(rows)} rows in html, {len(df)} in csv"
    # the JS sums these attributes, so they must reproduce the csv totals
    total = sum(float(x) for _, x, _ in rows)
    assert abs(total - df[TOTAL_XSEC].sum()) < 1e-6, (total, df[TOTAL_XSEC].sum())
    for cat in df["Category"].unique():
        got = sum(float(x) for c, x, _ in rows if c == cat)
        want = df.loc[df["Category"] == cat, TOTAL_XSEC].sum()
        assert abs(got - want) < 1e-6, (cat, got, want)
    assert all(os.path.exists(html.unescape(s))
               for s in re.findall(r'data-src="([^"]+)"', src)), "missing png"
    xs = [float(x) for _, x, _ in rows]
    assert xs == sorted(xs, reverse=True), "rows are not sorted by cross section"
    print(f"selfcheck ok: {len(rows)} rows, {len(df['Category'].unique())} categories")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        _selfcheck()
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else CSV)
