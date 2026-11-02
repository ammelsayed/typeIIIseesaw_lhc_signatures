#!/usr/bin/env python3
"""Build index.html: a filterable table of the decay chains with the
Feynman diagram of each row one click away.

Reads tables/decay_chains.csv for production xsecs and heavy-lepton BRs,
re-expands SM boson decays into a small set of *effective* channels
(Z/W/H with tau folding), and writes a self-contained index.html.

SM effective channels (ell = e or mu only):
  W -> ell nu : BR(W->e nu)+BR(W->mu nu)+BR(W->tau nu)*P(tau leptonic)
  W -> J      : BR(W->qq)+BR(W->tau nu)*P(tau hadronic)
  Z -> ell ell: BR(Z->ee)+BR(Z->mumu)+BR(Z->tautau)*P(both tau leptonic)
  Z -> J      : BR(Z->qq)+BR(Z->tautau)*P(both tau hadronic)
  H -> J      : H->gg+cc+bb + H->tautau*(both had) + H->WW*(both W had)
                + H->ZZ*(both Z had)
  H -> ell ell: H->mumu + H->tautau*(both lep) + H->WW*(both W lep)
                + H->ZZ*(one Z->ell ell, one Z->nu nu)
  H -> 4ell   : H->ZZ*(both Z->ell ell)

Tau BRs in the SM panel drive P(leptonic)=BR_e+BR_mu and P(hadronic)=BR_had
and live-update the effective SM BRs / table.

    python3 create_webpage.py
    python3 create_webpage.py --check
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

# Displayed table columns (no Production column).
COLS = ["Chain", "Prod. Xsec [fb]", "Br1", "Br11", "Br2", "Br22",
        "Total Cross Section [fb]", "xsec %"]
LABELS = ["Chain", "Prod. \u03c3 [fb]", "BR\u2081", "BR\u2081\u2081", "BR\u2082", "BR\u2082\u2082",
          "\u03c3 [fb]", "%"]
TOTAL_XSEC, PCT = "Total Cross Section [fb]", "xsec %"
PROD_XSEC = "Prod. Xsec [fb]"

PROD_LABEL = {
    "p p > sigp sig0": "pp \u2192 N\u207a N\u2070",
    "p p > sigm sig0": "pp \u2192 N\u207b N\u2070",
    "p p > sigp sigm": "pp \u2192 N\u207a N\u207b",
}
HL_LABEL = {
    "Npm > W nu": "N\u00b1 \u2192 W\u00b1 \u03bd",
    "Npm > Z l": "N\u00b1 \u2192 Z \u2113\u00b1",
    "Npm > H l": "N\u00b1 \u2192 H \u2113\u00b1",
    "sig0 > W l": "N\u2070 \u2192 W\u00b1 \u2113\u2213",
    "sig0 > z vl": "N\u2070 \u2192 Z \u03bd",
    "sig0 > h vl": "N\u2070 \u2192 H \u03bd",
}
# Map actual chain HL keys -> shared panel key (same BR).
HL_ALIAS = {
    "sigp > wp vl": "Npm > W nu",
    "sigm > wm vl": "Npm > W nu",
    "sigp > z lp": "Npm > Z l",
    "sigm > z lm": "Npm > Z l",
    "sigp > h lp": "Npm > H l",
    "sigm > h lm": "Npm > H l",
    "sig0 > wm lp": "sig0 > W l",
    "sig0 > wp lm": "sig0 > W l",
    "sig0 > z vl": "sig0 > z vl",
    "sig0 > h vl": "sig0 > h vl",
}
HL_PANEL_KEYS = [
    "Npm > W nu", "Npm > Z l", "Npm > H l",
    "sig0 > W l", "sig0 > z vl", "sig0 > h vl",
]

SM_EFF_LABEL = {
    "wp > lp vl": "W\u207a \u2192 \u2113\u207a \u03bd",
    "wp > J": "W\u207a \u2192 J",
    "wm > lm vl": "W\u207b \u2192 \u2113\u207b \u03bd\u0304",
    "wm > J": "W\u207b \u2192 J",
    "z > lp lm": "Z \u2192 \u2113\u207a \u2113\u207b",
    "z > J": "Z \u2192 J",
    "h > J": "H \u2192 J",
    "h > lp lm": "H \u2192 \u2113\u2113",
    "h > lp lm lp lm": "H \u2192 \u2113\u2113\u2113\u2113",
}
PIECE_LABEL = {
    "W > e nu": "W\u00b1 \u2192 e \u03bd",
    "W > mu nu": "W\u00b1 \u2192 \u03bc \u03bd",
    "W > ta nu": "W\u00b1 \u2192 \u03c4 \u03bd",
    "W > jj": "W\u00b1 \u2192 jj",
    "Z > ee": "Z \u2192 e\u207ae\u207b",
    "Z > mumu": "Z \u2192 \u03bc\u207a\u03bc\u207b",
    "Z > tautau": "Z \u2192 \u03c4\u207a\u03c4\u207b",
    "Z > jj": "Z \u2192 jj",
    "Z > nunu": "Z \u2192 \u03bd\u03bd\u0304",
    "H > gg": "H \u2192 gg",
    "H > cc": "H \u2192 c\u0304c",
    "H > bb": "H \u2192 b\u0304b",
    "H > tautau": "H \u2192 \u03c4\u207a\u03c4\u207b",
    "H > WW": "H \u2192 WW*",
    "H > ZZ": "H \u2192 ZZ*",
    "H > mumu": "H \u2192 \u03bc\u207a\u03bc\u207b",
    "tau > e vv": "\u03c4 \u2192 e \u03bd\u03bd",
    "tau > mu vv": "\u03c4 \u2192 \u03bc \u03bd\u03bd",
    "tau > J vv": "\u03c4 \u2192 j \u03bd\u03bd (hadronic)",
}
PIECE_DEFAULTS = OrderedDict([
    ("W > e nu", 0.1086),
    ("W > mu nu", 0.1086),
    ("W > ta nu", 0.1138),
    ("W > jj", 0.6741),
    ("Z > ee", 0.03363),
    ("Z > mumu", 0.03363),
    ("Z > tautau", 0.0337),
    ("Z > jj", 0.6991),
    ("Z > nunu", 0.2000),
    ("H > gg", 0.0818),
    ("H > cc", 0.0289),
    ("H > bb", 0.5824),
    ("H > tautau", 0.0627),
    ("H > WW", 0.2137),
    ("H > ZZ", 0.0264),
    ("H > mumu", 0.0002),
    ("tau > e vv", 0.1782),
    ("tau > mu vv", 0.1739),
    ("tau > J vv", 0.6479),
])
SM_EFF_KEYS = [
    "wp > lp vl", "wp > J",
    "wm > lm vl", "wm > J",
    "z > lp lm", "z > J",
    "h > J", "h > lp lm", "h > lp lm lp lm",
]
TAU_KEYS = ["tau > e vv", "tau > mu vv", "tau > J vv"]
PIECE_KEYS = list(PIECE_DEFAULTS.keys())

# Effective filter keys (merged W\u00b1) used by checkboxes; rows map via SM_FILTER.
SM_FILTER_KEYS = [
    "W > ell nu", "W > J",
    "z > lp lm", "z > J",
    "h > J", "h > lp lm", "h > lp lm lp lm",
]
SM_FILTER_LABEL = {
    "W > ell nu": "W\u00b1 \u2192 \u2113\u03bd",
    "W > J": "W\u00b1 \u2192 J",
    "z > lp lm": "Z \u2192 \u2113\u2113",
    "z > J": "Z \u2192 J",
    "h > J": "H \u2192 J",
    "h > lp lm": "H \u2192 \u2113\u2113",
    "h > lp lm lp lm": "H \u2192 \u2113\u2113\u2113\u2113",
}
SM_FILTER = {
    "wp > lp vl": "W > ell nu",
    "wm > lm vl": "W > ell nu",
    "wp > J": "W > J",
    "wm > J": "W > J",
    "z > lp lm": "z > lp lm",
    "z > J": "z > J",
    "h > J": "h > J",
    "h > lp lm": "h > lp lm",
    "h > lp lm lp lm": "h > lp lm lp lm",
}
# Map filter key -> representative effective BR key for the note % display
EFF_PCT_KEY = {
    "W > J": "wp > J",
    "W > ell nu": "wp > lp vl",
    "z > J": "z > J",
    "z > lp lm": "z > lp lm",
    "h > J": "h > J",
    "h > lp lm": "h > lp lm",
    "h > lp lm lp lm": "h > lp lm lp lm",
}

# Back-compat alias used in a few places
SM_LABEL = {**SM_EFF_LABEL, **PIECE_LABEL}

def pieces_from(values=None):
    out = OrderedDict((k, float(v)) for k, v in PIECE_DEFAULTS.items())
    if values:
        for k, v in values.items():
            if k in out:
                out[k] = float(v)
    return out


def effective_sm_brs(piece_vals=None):
    """Effective SM BRs from underlying piece BRs + tau folding."""
    p = pieces_from(piece_vals)
    p_lep = p["tau > e vv"] + p["tau > mu vv"]
    p_had = p["tau > J vv"]
    w_lep = p["W > e nu"] + p["W > mu nu"] + p["W > ta nu"] * p_lep
    w_had = p["W > jj"] + p["W > ta nu"] * p_had
    z_ll = p["Z > ee"] + p["Z > mumu"] + p["Z > tautau"] * (p_lep ** 2)
    z_had = p["Z > jj"] + p["Z > tautau"] * (p_had ** 2)
    h_j = (p["H > gg"] + p["H > cc"] + p["H > bb"] + p["H > tautau"] * (p_had ** 2)
           + p["H > WW"] * (p["W > jj"] ** 2)
           + p["H > ZZ"] * (p["Z > jj"] ** 2))
    h_ll = (p["H > mumu"] + p["H > tautau"] * (p_lep ** 2)
            + p["H > WW"] * (w_lep ** 2)
            + p["H > ZZ"] * 2.0 * z_ll * p["Z > nunu"])
    h_4l = p["H > ZZ"] * (z_ll ** 2)
    return OrderedDict([
        ("wp > lp vl", w_lep),
        ("wp > J", w_had),
        ("wm > lm vl", w_lep),
        ("wm > J", w_had),
        ("z > lp lm", z_ll),
        ("z > J", z_had),
        ("h > J", h_j),
        ("h > lp lm", h_ll),
        ("h > lp lm lp lm", h_4l),
    ])


def sm_channel_expansions(boson):
    """Effective final channels for one SM boson (no per-tau row split)."""
    # (sm_key, nL_add, nJ_add, lep_plus, lep_minus, diag_mode)
    if boson == "wp":
        return [
            ("wp > lp vl", 1, 0, 1, 0, "lp vl"),
            ("wp > J", 0, 1, 0, 0, "J"),
        ]
    if boson == "wm":
        return [
            ("wm > lm vl", 1, 0, 0, 1, "lm vl"),
            ("wm > J", 0, 1, 0, 0, "J"),
        ]
    if boson == "z":
        return [
            ("z > lp lm", 2, 0, 1, 1, "lp lm"),
            ("z > J", 0, 1, 0, 0, "J"),
        ]
    if boson == "h":
        return [
            ("h > J", 0, 1, 0, 0, "J"),
            ("h > lp lm", 2, 0, 1, 1, "lp lm"),
            ("h > lp lm lp lm", 4, 0, 2, 2, "lp lm lp lm"),
        ]
    raise KeyError(boson)


PAGE = """<!DOCTYPE html>
<meta charset="utf-8">
<title>Type-III seesaw decay chains</title>
<style>
 body{{margin:0;padding:32px 16px;color:#1a1a1a;background:#f3f4f6;
   font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
 #content{{max-width:1200px;margin:0 auto;padding:28px 32px 36px;background:#fff;
   border:1px solid #e5e7eb;border-radius:10px;box-shadow:0 1px 2px rgba(0,0,0,.04);
   box-sizing:border-box}}
 h1{{font-size:20px;font-weight:600;letter-spacing:-0.01em;margin:0 0 16px;color:#111}}
 h2{{font-size:13px;font-weight:600;margin:0 0 8px;color:#374151;text-transform:none}}
 .toolbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 12px}}
 .note{{color:#6b7280;font-size:12.5px;line-height:1.55;margin:0 0 10px}}
 .note.formulas{{background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;
   padding:10px 12px;margin:0 0 16px;color:#374151}}
 .note.formulas strong{{color:#111}}
 .note.formulas .eff-pct{{font-variant-numeric:tabular-nums;font-weight:600;color:#111}}
 .eff-filters{{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;
   margin:0 0 16px;padding:8px 10px;border:1px solid #e5e7eb;border-radius:8px;
   background:#fafafa;font-size:12.5px}}
 .eff-filters-lab{{font-weight:600;color:#374151;margin-right:4px}}
 .eff-filters label{{display:inline-flex;align-items:center;gap:5px;color:#1f2937;
   white-space:nowrap}}
 .subhead{{font-size:11.5px;font-weight:600;color:#6b7280;text-transform:uppercase;
   letter-spacing:.04em;margin:10px 0 4px}}

 table{{border-collapse:collapse;font-size:12.5px;width:100%;box-sizing:border-box}}
 th,td{{border:1px solid #e5e7eb;padding:5px 8px;text-align:left}}
 th{{background:#f9fafb;color:#374151;font-weight:600;position:sticky;top:0;z-index:1}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 tr.row:hover{{background:#f8fafc}}
 tr.hide{{display:none}}
 tfoot td{{font-weight:600;background:#f9fafb}}
 code{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px}}
 button{{font:inherit;padding:4px 10px;cursor:pointer;border:1px solid #d1d5db;
   border-radius:6px;background:#fff;color:#111}}
 button:hover{{background:#f9fafb}}
 select,input[type=number]{{font:inherit;padding:4px 6px;border:1px solid #d1d5db;
   border-radius:6px;background:#fff}}
 #panel{{display:flex;flex-direction:row;flex-wrap:nowrap;align-items:stretch;
   gap:12px;margin:0 0 20px;padding:0;border:none;background:transparent;
   width:100%;box-sizing:border-box}}
 #panel .box{{flex:1 1 0;min-width:0;background:#fafafa;border:1px solid #e5e7eb;
   border-radius:8px;padding:12px;overflow:visible}}
 #panel .box h2{{margin:0 0 10px;padding-bottom:6px;border-bottom:1px solid #e5e7eb}}
 #panel .box label.row{{display:grid;grid-template-columns:18px minmax(0,1fr) 7.25em;
   column-gap:8px;align-items:center;margin:0;padding:5px 0;
   border-bottom:1px solid #f0f0f0}}
 #panel .box label.row.piece{{grid-template-columns:minmax(0,1fr) 7.25em}}
 #panel .box label.row:last-child{{border-bottom:none}}
 #panel .box label.row span.lab{{min-width:0;color:#1f2937;line-height:1.35;
   overflow-wrap:anywhere}}
 #panel .box input.val, #panel .box span.val-ro{{width:100%;box-sizing:border-box;
   text-align:right;font-variant-numeric:tabular-nums}}
 #panel .box span.val-ro{{display:inline-block;padding:4px 6px;border:1px solid #e5e7eb;
   border-radius:6px;background:#f3f4f6;color:#111;font:inherit}}
 #lb{{display:none;position:fixed;inset:0;background:#000a;z-index:9;
      align-items:center;justify-content:center}}
 #lb.on{{display:flex}}
 #lb figure{{background:#fff;margin:0;padding:12px;border-radius:8px;
      max-width:92vw;max-height:92vh;display:flex;flex-direction:column;gap:8px;
      border:1px solid #e5e7eb}}
 #lb .bar{{display:flex;gap:6px;align-items:center}}
 #lb .bar .sp{{flex:1;font:12px ui-monospace,monospace;color:#6b7280;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
 #lb .frame{{overflow:auto;max-width:90vw;max-height:78vh;text-align:center}}
 #lb img{{transition:transform .12s;display:block;margin:auto}}
</style>

<div id="content">
<h1>Type-III seesaw &mdash; <span id="hn">{n}</span> decay chains</h1>

<div class="toolbar">
 <label>Category
  <select id="cat">
   <option value="">all ({n})</option>
   {options}
  </select>
 </label>
 <button type="button" id="allOn">select all modes</button>
 <button type="button" id="allOff">clear all modes</button>
 <button type="button" id="resetBr">reset values</button>
</div>

<p class="note">
 Toggle pair production, heavy-lepton, and effective SM decays.
 \u03c3 = \u03c3<sub>prod</sub> \u00d7 BR\u2081 \u00d7 BR\u2081\u2081 \u00d7 BR\u2082 \u00d7 BR\u2082\u2082; % among visible rows.
 Final-state \u2113 means e/\u03bc only. W/Z/H channels fold \u03c4 decays using the \u03c4 BRs at the bottom of the SM panel
 (both-\u03c4 leptonic \u2192 \u2113\u2113; both hadronic \u2192 J; H\u2192WW*/ZZ* both hadronic \u2192 H\u2192J; both leptonic \u2192 H\u2192\u2113\u2113 / H\u2192\u2113\u2113\u2113\u2113).
</p>
<p class="note formulas">
 <strong>Effective SM grouping</strong> (auto-updates from the underlying BRs in the SM panel):
 <br>Br(W\u2192J) = Br(W\u2192jj) + Br(W\u2192\u03c4\u03bd)\u00d7Br(\u03c4\u2192j\u03bd\u03bd) = <span class="eff-pct" data-eff="W > J">74.7831</span>%
 <br>Br(W\u2192\u2113\u03bd) = Br(W\u2192e\u03bd)+Br(W\u2192\u03bc\u03bd) + Br(W\u2192\u03c4\u03bd)\u00d7[Br(\u03c4\u2192e)+Br(\u03c4\u2192\u03bc)] = <span class="eff-pct" data-eff="W > ell nu">25.7269</span>%
 <br>Br(Z\u2192J) = Br(Z\u2192jj) + Br(Z\u2192\u03c4\u03c4)\u00d7[Br(\u03c4\u2192j\u03bd\u03bd)]<sup>2</sup> = <span class="eff-pct" data-eff="z > J">71.3246</span>%
 <br>Br(Z\u2192\u2113\u2113) = Br(Z\u2192ee)+Br(Z\u2192\u03bc\u03bc) + Br(Z\u2192\u03c4\u03c4)\u00d7[Br(\u03c4\u2192e)+Br(\u03c4\u2192\u03bc)]<sup>2</sup> = <span class="eff-pct" data-eff="z > lp lm">7.1438</span>%
 <br>Br(H\u2192J) = Br(H\u2192gg)+Br(H\u2192cc)+Br(H\u2192bb) + Br(H\u2192\u03c4\u03c4)\u00d7[Br(\u03c4\u2192j\u03bd\u03bd)]<sup>2</sup>
  + Br(H\u2192WW*)\u00d7[Br(W\u2192jj)]<sup>2</sup> + Br(H\u2192ZZ*)\u00d7[Br(Z\u2192jj)]<sup>2</sup> = <span class="eff-pct" data-eff="h > J">82.9430</span>%
 <br>Br(H\u2192\u2113\u2113) = Br(H\u2192\u03bc\u03bc) + Br(H\u2192\u03c4\u03c4)\u00d7[Br(\u03c4\u2192e)+Br(\u03c4\u2192\u03bc)]<sup>2</sup>
  + Br(H\u2192WW*)\u00d7[Br(W\u2192\u2113\u03bd)]<sup>2</sup>
  + Br(H\u2192ZZ*)\u00d72\u00d7Br(Z\u2192\u2113\u2113)\u00d7Br(Z\u2192\u03bd\u03bd) = <span class="eff-pct" data-eff="h > lp lm">2.2872</span>%
 <br>Br(H\u2192\u2113\u2113\u2113\u2113) = Br(H\u2192ZZ*)\u00d7[Br(Z\u2192\u2113\u2113)]<sup>2</sup> = <span class="eff-pct" data-eff="h > lp lm lp lm">0.0135</span>%
</p>
<div class="eff-filters" id="effFilters">
 <span class="eff-filters-lab">Filter SM channels</span>
 {eff_filters}
</div>



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
  <td colspan="7">Total <span id="tn"></span></td>
  <td class="num" id="tx"></td>
  <td class="num" id="tp"></td>
  <td></td>
 </tr></tfoot>
</table>
</div>

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
const DEFAULT_PIECES = {pieces_json};
const SM_EFF_KEYS = {sm_eff_json};
const PIECE_KEYS = {piece_json};
const TAU_KEYS = {tau_json};
const HL_ALIAS = {hl_alias_json};
const SM_FILTER = {sm_filter_json};
const EFF_PCT_KEY = {eff_pct_json};
const rows = [...document.querySelectorAll("tr.row")];
const sel = document.getElementById("cat");
const img = document.getElementById("lbi");
let scale = 1;

function brOf(key) {{
  // Shared panel key for charged N / N0 aliases
  const panelKey = HL_ALIAS[key] || key;
  const el = document.querySelector('input.val[data-key="' + CSS.escape(panelKey) + '"]');
  if (!el) return DEFAULT_BR[panelKey] ?? DEFAULT_BR[key] ?? DEFAULT_PIECES[key] ?? 1;
  const v = parseFloat(el.value);
  return Number.isFinite(v) && v >= 0 ? v : 0;
}}

function pieceOf(key) {{
  const el = document.querySelector('input.val.piece[data-key="' + CSS.escape(key) + '"]');
  if (!el) return DEFAULT_PIECES[key] ?? 0;
  const v = parseFloat(el.value);
  return Number.isFinite(v) && v >= 0 ? v : 0;
}}

function modeOn(kind, key) {{
  let k = key;
  if (kind === "hl") k = HL_ALIAS[key] || key;
  if (kind === "sm") k = SM_FILTER[key] || key;
  const el = document.querySelector('input.mode[data-kind="' + kind + '"][data-key="' + CSS.escape(k) + '"]');
  return el ? el.checked : true;
}}

function readPieces() {{
  const p = {{}};
  for (const k of PIECE_KEYS) p[k] = pieceOf(k);
  return p;
}}

function effectiveSm() {{
  const p = readPieces();
  const pLep = p["tau > e vv"] + p["tau > mu vv"];
  const pHad = p["tau > J vv"];
  const wLep = p["W > e nu"] + p["W > mu nu"] + p["W > ta nu"] * pLep;
  const wHad = p["W > jj"] + p["W > ta nu"] * pHad;
  const zLl = p["Z > ee"] + p["Z > mumu"] + p["Z > tautau"] * pLep * pLep;
  const zHad = p["Z > jj"] + p["Z > tautau"] * pHad * pHad;
  const hJ = p["H > gg"] + p["H > cc"] + p["H > bb"] + p["H > tautau"] * pHad * pHad
    + p["H > WW"] * p["W > jj"] * p["W > jj"]
    + p["H > ZZ"] * p["Z > jj"] * p["Z > jj"];
  const hLl = p["H > mumu"] + p["H > tautau"] * pLep * pLep
    + p["H > WW"] * wLep * wLep
    + p["H > ZZ"] * 2 * zLl * p["Z > nunu"];
  const h4l = p["H > ZZ"] * zLl * zLl;
  return {{
    "wp > lp vl": wLep,
    "wp > J": wHad,
    "wm > lm vl": wLep,
    "wm > J": wHad,
    "z > lp lm": zLl,
    "z > J": zHad,
    "h > J": hJ,
    "h > lp lm": hLl,
    "h > lp lm lp lm": h4l,
  }};
}}

function fmtPct(x) {{
  // value * 100 with sensible decimals
  const p = 100 * x;
  if (!Number.isFinite(p)) return "";
  let d = 4;
  if (Math.abs(p) >= 10) d = 4;
  if (Math.abs(p) >= 100) d = 2;
  if (Math.abs(p) < 0.01) d = 6;
  let s = p.toFixed(d);
  if (s.indexOf(".") >= 0) s = s.replace(/\\.0+$/, "").replace(/(\\.[0-9]*?)0+$/, "$1").replace(/\\.$/, "");
  return s;
}}

function syncEffective() {{
  const eff = effectiveSm();
  for (const [filt, effKey] of Object.entries(EFF_PCT_KEY)) {{
    const el = document.querySelector('span.eff-pct[data-eff="' + CSS.escape(filt) + '"]');
    if (el) el.textContent = fmtPct(eff[effKey]);
  }}
  return eff;
}}

function apply() {{
  const v = sel.value;
  let n = 0, s = 0;
  const visible = [];
  const eff = syncEffective();
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

    const px = brOf(prod);
    const br1 = brOf(hl1), br2 = brOf(hl2);
    const br11 = eff[sm1], br22 = eff[sm2];
    const xsec = px * br1 * br11 * br2 * br22;
    r.querySelector(".c-prodxsec").textContent = fmt(px);
    r.querySelector(".c-br1").textContent = fmt(br1);
    r.querySelector(".c-br11").textContent = fmt(br11);
    r.querySelector(".c-br2").textContent = fmt(br2);
    r.querySelector(".c-br22").textContent = fmt(br22);
    r.querySelector(".c-xsec").textContent = fmt(xsec);
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
  document.getElementById("tx").textContent = fmt(s);
  document.getElementById("tp").textContent = (n ? 100 : 0).toFixed(2) + "%";
}}

function fmt(x) {{
  if (!Number.isFinite(x)) return "";
  if (x === 0) return "0";
  const a = Math.abs(x);
  let d = 6;
  if (a >= 100) d = 3;
  else if (a >= 10) d = 4;
  else if (a >= 1) d = 5;
  let s = x.toFixed(d);
  if (s.indexOf(".") >= 0) s = s.replace(/\\.0+$/, "").replace(/(\\.[0-9]*?)0+$/, "$1").replace(/\\.$/, "");
  return s;
}}

sel.onchange = apply;
for (const el of document.querySelectorAll("input.mode, input.val")) {{
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
  document.querySelectorAll("input.val").forEach(el => {{
    const k = el.dataset.key;
    const v = (k in DEFAULT_PIECES) ? DEFAULT_PIECES[k] : DEFAULT_BR[k];
    el.value = fmt(v);
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
    """Fixed-decimal display for table cells (no scientific notation)."""
    if pd.isna(x):
        return ""
    x = float(x)
    if x == 0:
        return "0"
    a = abs(x)
    d = 6 if a < 1 else (5 if a < 10 else (4 if a < 100 else 3))
    s = f"{x:.{d}f}".rstrip("0").rstrip(".")
    return s or "0"


def _fmt_input(x):
    return fmt(x)


def _hl_key(heavy):
    return f"{heavy[0]} > {' '.join(heavy[1:])}"


def _controls(keys, kind, labels, values, *, value_title="branching ratio",
               max_value=1):
    lines = []
    max_attr = f' max="{max_value}"' if max_value is not None else ""
    for key in keys:
        lab = html.escape(labels.get(key, key))
        k = html.escape(key)
        val = values.get(key)
        if val is None:
            lines.append(
                f'<label class="row"><input class="mode" type="checkbox" '
                f'data-kind="{kind}" data-key="{k}" checked>'
                f'<span class="lab" title="{k}">{lab}</span></label>')
        else:
            lines.append(
                f'<label class="row"><input class="mode" type="checkbox" '
                f'data-kind="{kind}" data-key="{k}" checked>'
                f'<span class="lab" title="{k}">{lab}</span>'
                f'<input class="val" type="number" min="0"{max_attr} step="any" '
                f'data-key="{k}" value="{_fmt_input(val)}" '
                f'title="{html.escape(value_title)}"></label>')
    return "\n  ".join(lines)



def _sm_panel_html(piece_vals):
    """Editable underlying SM + tau BRs only (no effective BR editors)."""
    lines = []
    for key in PIECE_KEYS:
        lab = html.escape(PIECE_LABEL.get(key, key))
        k = html.escape(key)
        lines.append(
            f'<label class="row piece"><span class="lab" title="{k}">{lab}</span>'
            f'<input class="val piece" type="number" min="0" max="1" step="any" '
            f'data-key="{k}" value="{_fmt_input(piece_vals[key])}" '
            f'title="underlying branching ratio"></label>')
    return "\n  ".join(lines)


def _eff_filters_html():
    """Compact effective-channel toggles (filter only, no BR fields)."""
    parts = []
    for key in SM_FILTER_KEYS:
        lab = html.escape(SM_FILTER_LABEL.get(key, key))
        k = html.escape(key)
        parts.append(
            f'<label><input class="mode" type="checkbox" data-kind="sm" '
            f'data-key="{k}" checked> {lab}</label>')
    return "\n ".join(parts)



def _os_or_ss(nL, n_plus, n_minus):
    if nL != 2:
        return ""
    if n_plus == 1 and n_minus == 1:
        return "OS"
    return "SS"


def _heavy_lep_counts(heavy):
    lep = heavy[2]
    if lep == "lp":
        return 1, 0
    if lep == "lm":
        return 0, 1
    return 0, 0


def main(csv_path=CSV):
    df = pd.read_csv(csv_path)
    piece_vals = pieces_from()
    sm_br = effective_sm_brs(piece_vals)

    topologies = OrderedDict()
    for _, row in df.iterrows():
        _prod, heavy, sm = parse_chain(row.Chain)
        h1, h2 = _hl_key(heavy[0]), _hl_key(heavy[1])
        key = (row.Production, h1, h2)
        if key in topologies:
            continue
        topologies[key] = {
            "prod": row.Production,
            "heavy": heavy,
            "h1": h1,
            "h2": h2,
            "b1": sm[0][0],
            "b2": sm[1][0],
            "prodxsec": float(row[PROD_XSEC]),
            "br1": float(row.Br1),
            "br2": float(row.Br2),
        }

    hl_br = OrderedDict()
    records = []
    for topo in topologies.values():
        heavy = topo["heavy"]
        hp1, hm1 = _heavy_lep_counts(heavy[0])
        hp2, hm2 = _heavy_lep_counts(heavy[1])
        hl_br.setdefault(HL_ALIAS.get(topo["h1"], topo["h1"]), topo["br1"])
        hl_br.setdefault(HL_ALIAS.get(topo["h2"], topo["h2"]), topo["br2"])

        for sm1, nL1, nJ1, p1, m1, diag1 in sm_channel_expansions(topo["b1"]):
            for sm2, nL2, nJ2, p2, m2, diag2 in sm_channel_expansions(topo["b2"]):
                br11 = sm_br[sm1]
                br22 = sm_br[sm2]
                nL = nL1 + nL2 + hp1 + hm1 + hp2 + hm2
                n_plus = p1 + p2 + hp1 + hp2
                n_minus = m1 + m2 + hm1 + hm2
                nJ = nJ1 + nJ2
                sign = _os_or_ss(nL, n_plus, n_minus)
                cat = channel_dir(nL, sign, nJ)

                decay1, decay2 = topo["h1"], topo["h2"]
                chain = (f"{topo['prod']}, ({decay1}, {sm1}), ({decay2}, {sm2})")
                diag_chain = (
                    f"{topo['prod']}, ({decay1}, {topo['b1']} > {diag1}), "
                    f"({decay2}, {topo['b2']} > {diag2})")
                dname = diagram_name(diag_chain)
                xsec = topo["prodxsec"] * topo["br1"] * br11 * topo["br2"] * br22
                records.append({
                    "Production": topo["prod"],
                    "Chain": chain,
                    "Category": cat,
                    "Br1": topo["br1"],
                    "Br11": br11,
                    "Br2": topo["br2"],
                    "Br22": br22,
                    PROD_XSEC: topo["prodxsec"],
                    TOTAL_XSEC: xsec,
                    "h1": topo["h1"], "h2": topo["h2"],
                    "sm1": sm1, "sm2": sm2,
                    "diag_name": dname,
                })

    out = pd.DataFrame.from_records(records)
    out = out.sort_values(TOTAL_XSEC, ascending=False, kind="stable")
    total = out[TOTAL_XSEC].sum()
    out[PCT] = 100.0 * out[TOTAL_XSEC] / total if total else 0.0

    order = sorted(out["Category"].unique(),
                   key=lambda c: (int(c.split("L")[0].rstrip("OS")), c))

    prod_keys = sorted(out["Production"].unique())
    prod_xsec = OrderedDict()
    for topo in topologies.values():
        prod_xsec.setdefault(topo["prod"], topo["prodxsec"])
    prod_xsec = OrderedDict((k, prod_xsec[k]) for k in prod_keys)
    hl_keys = [k for k in HL_PANEL_KEYS if k in hl_br]
    default_br = {**prod_xsec, **hl_br, **sm_br, **piece_vals}

    rows, missing = [], 0
    for _, row in out.iterrows():
        cat = row.Category
        name = row.diag_name
        png = f"feynman_diagrams/{cat}/{name}.png"
        if not os.path.exists(os.path.join(HERE, png)):
            found = None
            fd = os.path.join(HERE, "feynman_diagrams")
            if os.path.isdir(fd):
                for sub in os.listdir(fd):
                    cand = os.path.join(fd, sub, f"{name}.png")
                    if os.path.isfile(cand):
                        found = f"feynman_diagrams/{sub}/{name}.png"
                        break
            if found:
                png = found
            else:
                missing += 1

        tds = [f"<td>{html.escape(cat)}</td>"]
        for col in COLS:
            if col == "Chain":
                tds.append(f"<td><code>{html.escape(str(row.Chain))}</code></td>")
            elif col == "Br1":
                tds.append(f'<td class="num c-br1">{fmt(row.Br1)}</td>')
            elif col == "Br11":
                tds.append(f'<td class="num c-br11">{fmt(row.Br11)}</td>')
            elif col == "Br2":
                tds.append(f'<td class="num c-br2">{fmt(row.Br2)}</td>')
            elif col == "Br22":
                tds.append(f'<td class="num c-br22">{fmt(row.Br22)}</td>')
            elif col == TOTAL_XSEC:
                tds.append(f'<td class="num c-xsec">{fmt(row[TOTAL_XSEC])}</td>')
            elif col == PCT:
                tds.append(f'<td class="num c-pct">{fmt(row[PCT])}</td>')
            elif col == PROD_XSEC:
                tds.append(f'<td class="num c-prodxsec">{fmt(row[PROD_XSEC])}</td>')
            else:
                tds.append("<td></td>")
        tds.append(f'<td><button data-src="{html.escape(png)}" '
                   f'data-name="{html.escape(name)}">diagram</button></td>')
        rows.append(
            f'<tr class="row" data-cat="{html.escape(cat)}" '
            f'data-prod="{html.escape(row.Production)}" '
            f'data-hl1="{html.escape(row.h1)}" data-hl2="{html.escape(row.h2)}" '
            f'data-sm1="{html.escape(row.sm1)}" data-sm2="{html.escape(row.sm2)}" '
            f'data-prodxsec="{row[PROD_XSEC]}" '
            f'data-xsec="{row[TOTAL_XSEC]}" '
            f'data-pct="{row[PCT]}">{"".join(tds)}</tr>')

    options = "\n  ".join(
        f'<option value="{html.escape(c)}">{html.escape(c)} '
        f'({int((out.Category == c).sum())})</option>'
        for c in order)

    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(PAGE.format(
            n=len(out),
            options=options,
            head="".join(f"<th>{html.escape(l)}</th>" for l in LABELS),
            rows="\n".join(rows),
            prod_controls=_controls(
                prod_keys, "prod", PROD_LABEL, prod_xsec,
                value_title="production cross section [fb]", max_value=None),
            hl_controls=_controls(hl_keys, "hl", HL_LABEL, hl_br),
            sm_controls=_sm_panel_html(piece_vals),
            eff_filters=_eff_filters_html(),
            br_json=json.dumps(default_br),
            pieces_json=json.dumps(dict(piece_vals)),
            sm_eff_json=json.dumps(SM_EFF_KEYS),
            piece_json=json.dumps(PIECE_KEYS),
            tau_json=json.dumps(TAU_KEYS),
            hl_alias_json=json.dumps(HL_ALIAS),
            sm_filter_json=json.dumps(SM_FILTER),
            eff_pct_json=json.dumps(EFF_PCT_KEY),
        ))
    print(f"{len(out)} rows, {len(order)} categories -> {INDEX}"
          + (f" ({missing} missing PNGs)" if missing else ""))


def _selfcheck(csv_path=CSV):
    import re
    src = open(INDEX, encoding="utf-8").read()
    rows = re.findall(
        r'data-cat="([^"]+)" data-prod="([^"]+)" data-hl1="([^"]+)" data-hl2="([^"]+)" '
        r'data-sm1="([^"]+)" data-sm2="([^"]+)" data-prodxsec="([^"]+)" '
        r'data-xsec="([^"]+)" data-pct="([^"]+)"',
        src)
    assert rows, "no rows parsed"
    assert "Production" not in re.search(r"<thead>.*?</thead>", src, re.S).group(0)
    assert 'data-kind="prod"' in src and 'data-kind="hl"' in src and 'data-kind="sm"' in src
    assert "DEFAULT_PIECES" in src and "effectiveSm" in src and "HL_ALIAS" in src
    assert "eff-pct" in src and "EFF_PCT_KEY" in src
    assert "tau &gt; e vv" in src or "tau > e vv" in src
    assert "z &gt; ta+ ta-" not in src and "wp &gt; ta+ vt" not in src
    assert "N&amp;plusmn;" in src or "N&plusmn;" in src or "N\u00b1" in src or "N\pm" in src
    assert "W&amp;plusmn;" in src or "W&plusmn;" in src or "W\u00b1" in src or "W\pm" in src
    assert "Effective channels" not in src or "eff-filters" in src
    box_css = re.search(r"#panel \.box\{[^}]+\}", src).group(0)
    assert "max-height" not in box_css

    br_match = re.search(r"const DEFAULT_BR = (\{.*?\});", src)
    assert br_match
    default_br = json.loads(br_match.group(1))
    # DEFAULT_BR holds prod+HL panel keys + pieces + tau; effective live-computed
    for k in HL_PANEL_KEYS:
        assert k in default_br, k
    for k in PIECE_KEYS:
        assert k in default_br, k
        assert abs(default_br[k] - PIECE_DEFAULTS[k]) < 1e-12, k
    assert "note formulas" in src
    assert "Br(W" in src and "Br(Z" in src and "Br(H" in src
    # Live % in note
    for filt in ("W > J", "W > ell nu", "z > J", "z > lp lm", "h > J", "h > lp lm", "h > lp lm lp lm"):
        assert f'data-eff="{filt}"' in src, filt

    # Only effective SM keys appear on rows
    for *_, sm1, sm2, px, xsec, pct in rows:
        sm1, sm2 = html.unescape(sm1), html.unescape(sm2)
        assert sm1 in SM_EFF_KEYS and sm2 in SM_EFF_KEYS

    eff = effective_sm_brs()
    for cat, prod, hl1, hl2, sm1, sm2, px, xsec, pct in rows:
        prod = html.unescape(prod)
        hl1, hl2 = html.unescape(hl1), html.unescape(hl2)
        sm1, sm2 = html.unescape(sm1), html.unescape(sm2)
        h1 = HL_ALIAS.get(hl1, hl1)
        h2 = HL_ALIAS.get(hl2, hl2)
        want = (default_br[prod] * default_br[h1] * eff[sm1]
                * default_br[h2] * eff[sm2])
        assert abs(want - float(xsec)) < 1e-6, (cat, want, xsec, h1, h2, sm1, sm2)

    xs = [float(r[-2]) for r in rows]
    assert xs == sorted(xs, reverse=True)
    cats = {r[0] for r in rows}
    print(f"selfcheck ok: {len(rows)} rows, {len(cats)} categories")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        _selfcheck()
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else CSV)
