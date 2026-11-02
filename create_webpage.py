#!/usr/bin/env python3
"""Build index.html: a filterable table of the decay chains with the
Feynman diagram of each row one click away.

Reads tables/decay_chains.csv, reuses the naming from
draw_feynman_diagrams.py so the image paths line up, and writes a single
self-contained index.html next to it (no CDN, works offline).

The page lets you toggle allowed pair-production modes, heavy-lepton
decays, and SM-boson decays, and edit each mode's branching ratio; the
table cross sections and % update live.

    python3 create_webpage.py
"""

import html
import json
import os
import sys
from collections import OrderedDict

import pandas as pd

from draw_feynman_diagrams import CSV, channel_dir, diagram_name, parse_chain

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")

# nL, 2L_Sign and nJ are replaced by Category.
COLS = ["Production", "Chain", "Prod. Xsec [fb]", "Br1", "Br11", "Br2", "Br22",
        "Total Cross Section [fb]", "xsec %"]
LABELS = ["Production", "Chain", "Prod. σ [fb]", "BR₁", "BR₁₁", "BR₂", "BR₂₂",
          "σ [fb]", "%"]
TOTAL_XSEC, PCT = "Total Cross Section [fb]", "xsec %"
PROD_XSEC = "Prod. Xsec [fb]"

# Pretty labels for the control panel (MadGraph keys stay as data values).
PROD_LABEL = {
    "p p > sigp sig0": "pp → N⁺ N⁰",
    "p p > sigm sig0": "pp → N⁻ N⁰",
    "p p > sigp sigm": "pp → N⁺ N⁻",
}
HL_LABEL = {
    "sigp > wp vl": "N⁺ → W⁺ ν",
    "sigp > z lp": "N⁺ → Z ℓ⁺",
    "sigp > h lp": "N⁺ → H ℓ⁺",
    "sigm > wm vl": "N⁻ → W⁻ ν̄",
    "sigm > z lm": "N⁻ → Z ℓ⁻",
    "sigm > h lm": "N⁻ → H ℓ⁻",
    "sig0 > wm lp": "N⁰ → W⁻ ℓ⁺",
    "sig0 > wp lm": "N⁰ → W⁺ ℓ⁻",
    "sig0 > z vl": "N⁰ → Z ν",
    "sig0 > h vl": "N⁰ → H ν",
}
SM_LABEL = {
    "wp > lp vl": "W⁺ → ℓ⁺ ν",
    "wp > J": "W⁺ → jj",
    "wm > lm vl": "W⁻ → ℓ⁻ ν̄",
    "wm > J": "W⁻ → jj",
    "z > lp lm": "Z → ℓ⁺ ℓ⁻",
    "z > vl vl": "Z → ν ν̄",
    "z > J": "Z → jj",
    "h > lp lm": "H → ℓ⁺ ℓ⁻",
    "h > lp lm lp lm": "H → 4ℓ",
    "h > vl vl": "H → ν ν̄",
    "h > J": "H → bb̄",
}


PAGE = """<!DOCTYPE html>
<meta charset="utf-8">
<title>Type-III seesaw decay chains</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;color:#222}}
 h1{{font-size:18px;margin:0 0 12px}}
 h2{{font-size:14px;margin:14px 0 6px}}
 table{{border-collapse:collapse;font-size:13px}}
 th,td{{border:1px solid #ccc;padding:3px 7px;text-align:left}}
 th{{background:#f0f0f0;position:sticky;top:0;z-index:1}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 tr.row:hover{{background:#f7f9ff}}
 tr.hide{{display:none}}
 tfoot td{{font-weight:600;background:#fafafa}}
 code{{font-family:ui-monospace,monospace;font-size:12px}}
 button{{font:inherit;padding:2px 8px;cursor:pointer}}
 select,input[type=number]{{font:inherit;padding:3px}}
 input[type=number]{{width:7.5em}}
 #panel{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
   gap:12px 18px;margin:0 0 16px;padding:12px;border:1px solid #ddd;
   border-radius:8px;background:#fafafa}}
 #panel .box{{background:#fff;border:1px solid #e5e5e5;border-radius:6px;padding:8px 10px}}
 #panel .box label.row{{display:flex;align-items:center;gap:6px;margin:3px 0;
   flex-wrap:wrap}}
 #panel .box label.row span.lab{{flex:1;min-width:7em}}
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

<h1>Type-III seesaw &mdash; <span id="hn">{n}</span> decay chains</h1>

<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px">
 <label>Category
  <select id="cat">
   <option value="">all ({n})</option>
   {options}
  </select>
 </label>
 <button type="button" id="allOn">select all modes</button>
 <button type="button" id="allOff">clear all modes</button>
 <button type="button" id="resetBr">reset BRs</button>
</div>

<p style="color:#666;font-size:12px;margin:0 0 10px">
 Toggle which pair-production, heavy-lepton, and SM-boson decays are allowed.
 Edit a BR to rescale every chain that uses that mode
 (σ = σ<sub>prod</sub> × BR₁ × BR₁₁ × BR₂ × BR₂₂); % is renormalized among visible rows.
</p>

<div id="panel">
 <div class="box">
  <h2>Pair production</h2>
  {prod_controls}
 </div>
 <div class="box">
  <h2>Heavy-lepton decays</h2>
  {hl_controls}
 </div>
 <div class="box">
  <h2>SM boson decays</h2>
  {sm_controls}
 </div>
</div>

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
const DEFAULT_BR = {br_json};
const rows = [...document.querySelectorAll("tr.row")];
const sel = document.getElementById("cat");
const img = document.getElementById("lbi");
let scale = 1;

function brOf(key) {{
  const el = document.querySelector('input.br[data-key="' + CSS.escape(key) + '"]');
  if (!el) return DEFAULT_BR[key] || 1;
  const v = parseFloat(el.value);
  return Number.isFinite(v) && v >= 0 ? v : 0;
}}

function modeOn(kind, key) {{
  const el = document.querySelector('input.mode[data-kind="' + kind + '"][data-key="' + CSS.escape(key) + '"]');
  return el ? el.checked : true;
}}

function apply() {{
  const v = sel.value;
  let n = 0, s = 0;
  const visible = [];
  for (const r of rows) {{
    const prod = r.dataset.prod;
    const hl1 = r.dataset.hl1, hl2 = r.dataset.hl2;
    const sm1 = r.dataset.sm1, sm2 = r.dataset.sm2;
    const catOk = !v || r.dataset.cat === v;
    const modesOk = modeOn("prod", prod)
      && modeOn("hl", hl1) && modeOn("hl", hl2)
      && modeOn("sm", sm1) && modeOn("sm", sm2);
    const on = catOk && modesOk;
    r.classList.toggle("hide", !on);
    if (!on) continue;

    const br1 = brOf(hl1), br11 = brOf(sm1), br2 = brOf(hl2), br22 = brOf(sm2);
    const xsec = (+r.dataset.prodxsec) * br1 * br11 * br2 * br22;
    r.querySelector(".c-br1").textContent = fmt(br1);
    r.querySelector(".c-br11").textContent = fmt(br11);
    r.querySelector(".c-br2").textContent = fmt(br2);
    r.querySelector(".c-br22").textContent = fmt(br22);
    r.querySelector(".c-xsec").textContent = xsec.toFixed(4);
    r.dataset.xsec = String(xsec);
    visible.push(r);
    n++; s += xsec;
  }}
  for (const r of visible) {{
    const pct = s > 0 ? 100 * (+r.dataset.xsec) / s : 0;
    r.querySelector(".c-pct").textContent = pct.toFixed(2) + "%";
    r.dataset.pct = String(pct);
  }}
  document.getElementById("hn").textContent = String(n);
  document.getElementById("tn").textContent = "(" + n + ")";
  document.getElementById("tx").textContent = s.toFixed(4);
  document.getElementById("tp").textContent = (n ? 100 : 0).toFixed(2) + "%";
}}

function fmt(x) {{
  if (!Number.isFinite(x)) return "";
  const a = Math.abs(x);
  if (a !== 0 && (a >= 1e4 || a < 1e-3)) return x.toExponential(4).replace(/e\\+?/, "e");
  return String(+x.toPrecision(4));
}}

sel.onchange = apply;
for (const el of document.querySelectorAll("input.mode, input.br")) {{
  el.addEventListener("change", apply);
  el.addEventListener("input", apply);
}}
document.getElementById("allOn").onclick = () => {{
  document.querySelectorAll("input.mode").forEach(c => {{ c.checked = true; }});
  apply();
}};
document.getElementById("allOff").onclick = () => {{
  document.querySelectorAll("input.mode").forEach(c => {{ c.checked = false; }});
  apply();
}};
document.getElementById("resetBr").onclick = () => {{
  document.querySelectorAll("input.br").forEach(el => {{
    el.value = DEFAULT_BR[el.dataset.key];
  }});
  apply();
}};

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


def _hl_key(heavy):
    return f"{heavy[0]} > {' '.join(heavy[1:])}"


def _sm_key(sm):
    return f"{sm[0]} > {sm[1]}"


def _controls(keys, kind, labels, brs):
    """Checkbox (+ optional BR input) for each mode key."""
    lines = []
    for key in keys:
        lab = html.escape(labels.get(key, key))
        k = html.escape(key)
        br = brs.get(key)
        if br is None:
            lines.append(
                f'<label class="row"><input class="mode" type="checkbox" '
                f'data-kind="{kind}" data-key="{k}" checked>'
                f'<span class="lab" title="{k}">{lab}</span></label>')
        else:
            lines.append(
                f'<label class="row"><input class="mode" type="checkbox" '
                f'data-kind="{kind}" data-key="{k}" checked>'
                f'<span class="lab" title="{k}">{lab}</span>'
                f'<input class="br" type="number" min="0" max="1" step="any" '
                f'data-key="{k}" value="{br}" title="branching ratio"></label>')
    return "\n  ".join(lines)


def main(csv_path=CSV):
    df = pd.read_csv(csv_path)
    df["Category"] = [channel_dir(r.nL, r._3, r.nJ) for r in df.itertuples(index=False)]

    # largest cross section first, so the dominant channels sit at the top
    df = df.sort_values(TOTAL_XSEC, ascending=False, kind="stable")
    order = sorted(df["Category"].unique(),
                   key=lambda c: (int(c.split("L")[0].rstrip("OS")), c))

    prod_keys = sorted(df["Production"].unique())
    hl_br, sm_br = OrderedDict(), OrderedDict()
    parsed = []
    for row in df.itertuples(index=False):
        _prod, heavy, sm = parse_chain(row.Chain)
        h1, h2 = _hl_key(heavy[0]), _hl_key(heavy[1])
        s1, s2 = _sm_key(sm[0]), _sm_key(sm[1])
        hl_br.setdefault(h1, float(row.Br1))
        hl_br.setdefault(h2, float(row.Br2))
        sm_br.setdefault(s1, float(row.Br11))
        sm_br.setdefault(s2, float(row.Br22))
        parsed.append((h1, h2, s1, s2))

    # Stable, readable order in the panel.
    hl_keys = sorted(hl_br.keys(), key=lambda k: (k.split(">", 1)[0].strip(), k))
    sm_keys = sorted(sm_br.keys(), key=lambda k: (k.split(">", 1)[0].strip(), k))
    default_br = {**hl_br, **sm_br}

    rows, missing = [], 0
    for row, (h1, h2, s1, s2) in zip(df.itertuples(index=False), parsed):
        cat = row.Category
        name = diagram_name(row.Chain)
        png = f"feynman_diagrams/{cat}/{name}.png"
        if not os.path.exists(os.path.join(HERE, png)):
            missing += 1
        prod = row.Production
        tds = [f"<td>{html.escape(cat)}</td>"]
        for col in COLS:
            v = row[df.columns.get_loc(col)]
            if col in ("Production", "Chain"):
                tds.append(f"<td><code>{html.escape(str(v))}</code></td>")
            elif col == "Br1":
                tds.append(f'<td class="num c-br1">{fmt(v)}</td>')
            elif col == "Br11":
                tds.append(f'<td class="num c-br11">{fmt(v)}</td>')
            elif col == "Br2":
                tds.append(f'<td class="num c-br2">{fmt(v)}</td>')
            elif col == "Br22":
                tds.append(f'<td class="num c-br22">{fmt(v)}</td>')
            elif col == TOTAL_XSEC:
                tds.append(f'<td class="num c-xsec">{fmt(v)}</td>')
            elif col == PCT:
                tds.append(f'<td class="num c-pct">{fmt(v)}</td>')
            else:
                tds.append(f'<td class="num">{fmt(v)}</td>')
        tds.append(f'<td><button data-src="{html.escape(png)}" '
                   f'data-name="{html.escape(name)}">diagram</button></td>')
        rows.append(
            f'<tr class="row" data-cat="{html.escape(cat)}" '
            f'data-prod="{html.escape(prod)}" '
            f'data-hl1="{html.escape(h1)}" data-hl2="{html.escape(h2)}" '
            f'data-sm1="{html.escape(s1)}" data-sm2="{html.escape(s2)}" '
            f'data-prodxsec="{row[df.columns.get_loc(PROD_XSEC)]}" '
            f'data-xsec="{row[df.columns.get_loc(TOTAL_XSEC)]}" '
            f'data-pct="{row[df.columns.get_loc(PCT)]}">{"".join(tds)}</tr>')

    options = "\n  ".join(
        f'<option value="{html.escape(c)}">{html.escape(c)} ({int((df.Category == c).sum())})</option>'
        for c in order)

    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(PAGE.format(
            n=len(df),
            options=options,
            head="".join(f"<th>{html.escape(l)}</th>" for l in LABELS),
            rows="\n".join(rows),
            prod_controls=_controls(prod_keys, "prod", PROD_LABEL, {}),
            hl_controls=_controls(hl_keys, "hl", HL_LABEL, hl_br),
            sm_controls=_controls(sm_keys, "sm", SM_LABEL, sm_br),
            br_json=json.dumps(default_br),
        ))
    print(f"{len(df)} rows, {len(order)} categories -> {INDEX}"
          + (f" ({missing} missing PNGs)" if missing else ""))


def _selfcheck(csv_path=CSV):
    """Check the page's totals against pandas: python3 create_webpage.py --check"""
    import re
    df = pd.read_csv(csv_path)
    df["Category"] = [channel_dir(r.nL, r._3, r.nJ) for r in df.itertuples(index=False)]
    src = open(INDEX, encoding="utf-8").read()
    rows = re.findall(
        r'data-cat="([^"]+)" data-prod="([^"]+)" data-hl1="([^"]+)" data-hl2="([^"]+)" '
        r'data-sm1="([^"]+)" data-sm2="([^"]+)" data-prodxsec="([^"]+)" '
        r'data-xsec="([^"]+)" data-pct="([^"]+)"',
        src)
    assert len(rows) == len(df), f"{len(rows)} rows in html, {len(df)} in csv"
    total = sum(float(x) for *_, x, _p in rows)
    assert abs(total - df[TOTAL_XSEC].sum()) < 1e-6, (total, df[TOTAL_XSEC].sum())
    for cat in df["Category"].unique():
        got = sum(float(x) for c, *_, x, _p in rows if c == cat)
        want = df.loc[df["Category"] == cat, TOTAL_XSEC].sum()
        assert abs(got - want) < 1e-6, (cat, got, want)
    assert all(os.path.exists(html.unescape(s))
               for s in re.findall(r'data-src="([^"]+)"', src)), "missing png"
    xs = [float(x) for *_, x, _p in rows]
    assert xs == sorted(xs, reverse=True), "rows are not sorted by cross section"
    assert 'data-kind="prod"' in src and 'data-kind="hl"' in src and 'data-kind="sm"' in src
    assert "DEFAULT_BR" in src
    print(f"selfcheck ok: {len(rows)} rows, {len(df['Category'].unique())} categories")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        _selfcheck()
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else CSV)
