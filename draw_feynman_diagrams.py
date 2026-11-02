#!/usr/bin/env python3
"""Draw Feynman diagrams for the Type-III seesaw decay chains.

Reads tables/decay_chains.csv (written by read_results.ipynb with
decay_mode="decay_all", i.e. the SM boson decays included) and writes one
Asymptote file per chain into feynman_diagrams/<channel>/<process>.asy,
then renders each to .png beside it.

    python3 draw_feynman_diagrams.py [chains.csv]
"""

import os
import re
import subprocess
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "tables", "decay_chains.csv")
OUT = os.path.join(HERE, "feynman_diagrams")

HEAVY = {"sigp": r"$N^+$", "sigm": r"$N^-$", "sig0": r"$N^0$"}
LEPTON = {"lp": r"$\ell^+$", "lm": r"$\ell^-$", "vl": r"$\nu$"}
BOSON = {"wp": r"$W^+$", "wm": r"$W^-$", "z": r"$Z$", "h": r"$H$"}
# W and Z are vectors (wavy), H is a scalar (dashed).
BOSON_LINE = {"wp": "drawPhoton", "wm": "drawPhoton", "z": "drawPhoton", "h": "drawScalar"}

# (boson, daughters) -> the two daughter labels. An unknown mode raises
# KeyError instead of drawing a wrong label.
SM_DAUGHTERS = {
    ("wp", "lp vl"): (r"$\ell^+$", r"$\nu$"),
    ("wp", "J"): (r"$q$", r"$\bar{q}'$"),
    ("wm", "lm vl"): (r"$\ell^-$", r"$\bar{\nu}$"),
    ("wm", "J"): (r"$q'$", r"$\bar{q}$"),
    ("z", "lp lm"): (r"$\ell^+$", r"$\ell^-$"),
    ("z", "vl vl"): (r"$\nu$", r"$\bar{\nu}$"),
    ("z", "J"): (r"$q$", r"$\bar{q}$"),
    ("h", "lp lm"): (r"$\ell^+$", r"$\ell^-$"),
    ("h", "lp lm lp lm"): (r"$\ell^+\ell^-$", r"$\ell^+\ell^-$"),
    ("h", "vl vl"): (r"$\nu$", r"$\bar{\nu}$"),
    ("h", "J"): (r"$b$", r"$\bar{b}$"),
}

# every "A > B" in the chain, B stopping at the next comma or closing paren
_CHAIN_RE = re.compile(r"([\w\s]+?)\s*>\s*([\w\s]+?)(?=[,)]|$)")


def parse_chain(chain):
    """Split a chain into (production, (h1, sm1), (h2, sm2))."""
    parts = [(a.strip(), b.strip()) for a, b in _CHAIN_RE.findall(chain)]
    if len(parts) != 5:
        raise ValueError(f"expected 1 production + 2 heavy + 2 SM decays, got {len(parts)}: {chain}")
    prod = parts[0][1].split()
    heavy = [(parts[1][0], *parts[1][1].split()), (parts[3][0], *parts[3][1].split())]
    sm = [parts[2], parts[4]]
    return prod, heavy, sm


def diagram_name(chain):
    """pp2sigpsigm_sigp2zlp_sigm2zlm_z2lplm_z2lplm"""
    return "_".join(f"{a.replace(' ', '')}2{b.replace(' ', '')}" for a, b in _CHAIN_RE.findall(chain))


def channel_dir(nL, sign, nJ):
    """2OSL_1J, 2SSL_2J, 1L_2J, 0L_0J"""
    tag = f"2{sign}" if nL == 2 else str(nL)
    return f"{tag}L_{nJ}J"


def asy_source(prod, heavy, sm):
    (s1, b1, l1), (s2, b2, l2) = heavy
    (d1a, d1b), (d2a, d2b) = SM_DAUGHTERS[(b1, sm[0][1])], SM_DAUGHTERS[(b2, sm[1][1])]

    if set(prod) == {"sigp", "sigm"}:  # s-channel gamma*/Z*
        mediator, q_in = r"$\gamma^*/Z^*$", r"$\bar{q}$"
    else:  # charged-current W* exchange
        mediator = r"${W^+}^*$" if "sigp" in prod else r"${W^-}^*$"
        q_in = r"$\bar{q}'$"

    return f"""import feynman;

currentpen = linewidth(0.75);
fmdefaults();

real L = 50;

pair zl = (-0.75*L, 0);
pair zr = (+0.75*L, 0);

pair xu = zl + L*dir(120);
pair xl = zl + L*dir(-120);

pair yu = zr + L*dir(60);
pair yl = zr + L*dir(-60);

pair a = yu + L*dir(60);
pair b = yu + 1.5*L;

pair c = b + L*dir(30);
pair d = b + L*dir(-30);

pair a2 = yl + L*dir(-60);
pair b2 = yl + 1.5*L;

pair c2 = b2 + L*dir(30);
pair d2 = b2 + L*dir(-30);

// production
drawFermion(zl--xu);
drawFermion(xl--zl);
drawPhoton(zl--zr);

// heavy leptons
drawFermion(zr--yu);
drawFermion(zr--yl);

// {s1} decay
drawFermion(yu--a);
{BOSON_LINE[b1]}(yu--b);
drawFermion(b--c);
drawFermion(b--d);

// {s2} decay
drawFermion(yl--a2);
{BOSON_LINE[b2]}(yl--b2);
drawFermion(b2--c2);
drawFermion(b2--d2);

dot(zl, linewidth(3));
dot(zr, linewidth(3));
dot(yu, linewidth(3));
dot(yl, linewidth(3));
dot(b, linewidth(3));
dot(b2, linewidth(3));

label("{q_in}", xu, left);
label("$q$", xl, left);

label("{mediator}", zl--zr, up);

label("{HEAVY[s1]}", zr--yu, left);
label("{HEAVY[s2]}", zr--yl, left);

label("{LEPTON[l1]}", a, right);
label("{BOSON[b1]}", yu--b, down);

label("{d1a}", c, right);
label("{d1b}", d, right);

label("{LEPTON[l2]}", a2, right);
label("{BOSON[b2]}", yl--b2, up);

label("{d2a}", c2, right);
label("{d2b}", d2, right);
"""


def asy_generate_png(path):
    """Render a .asy file to a .png in the same directory."""
    # -o would append .png to the given name, so let asy derive it from the input
    subprocess.run(
        ["asy", "-f", "png", "-render", "3", "-quiet", os.path.basename(path)],
        cwd=os.path.dirname(path) or ".",
        check=True,
    )


def _selfcheck():
    """Assert-based check of the pure helpers: python3 draw_feynman_diagrams.py --check"""
    chain = "p p > sigp sig0, (sigp > wp vl, wp > lp vl), (sig0 > wm lp, wm > lm vl)"
    assert parse_chain(chain) == (
        ["sigp", "sig0"],
        [("sigp", "wp", "vl"), ("sig0", "wm", "lp")],
        [("wp", "lp vl"), ("wm", "lm vl")],
    )
    assert diagram_name(chain) == "pp2sigpsig0_sigp2wpvl_wp2lpvl_sig02wmlp_wm2lmvl"
    assert channel_dir(2, "OS", 1) == "2OSL_1J"
    assert channel_dir(2, "SS", 2) == "2SSL_2J"
    assert channel_dir(1, "", 2) == "1L_2J"
    assert channel_dir(0, "", 0) == "0L_0J"
    print("selfcheck ok")


def main(csv_path=CSV):
    df = pd.read_csv(csv_path)
    names = {}
    for row in df.itertuples(index=False):
        chain = row.Chain
        name = diagram_name(chain)
        if name in names:  # a collision would silently overwrite a diagram
            raise ValueError(f"duplicate diagram name {name!r}:\n  {names[name]}\n  {chain}")
        names[name] = chain

        prod, heavy, sm = parse_chain(chain)
        directory = os.path.join(OUT, channel_dir(row.nL, row._3, row.nJ))
        os.makedirs(directory, exist_ok=True)
        asy = os.path.join(directory, name + ".asy")
        with open(asy, "w") as f:
            f.write(asy_source(prod, heavy, sm))
        asy_generate_png(asy)

    print(f"{len(names)} diagrams written under {OUT}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        _selfcheck()
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else CSV)
