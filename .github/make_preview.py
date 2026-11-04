#!/usr/bin/env python3
"""Generate the Iosevka Heiskr README preview as an outlined SVG.

Every glyph is converted to a path, so the SVG needs no installed font and
stays sharp at any zoom. Each unique glyph is defined once in <defs> and
placed with <use>.

Usage:
    brew install svgo  # optional, cuts file size by about a third
    python3 -m venv venv && venv/bin/pip install fonttools uharfbuzz
    venv/bin/python make_preview.py [--fonts ~/Library/Fonts] [--out preview.svg]
"""

import argparse
import os
import shutil
import string
import subprocess

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

WEIGHTS = ["Thin", "ExtraLight", "Light", "Regular", "Medium",
           "SemiBold", "Bold", "ExtraBold", "Heavy"]

# Off-white rather than white, so it isn't a glaring block in GitHub dark mode.
BG = "#dedbd3"
FG = "#303236"
LABEL = "#5a5d63"
RULE = "#c4c0b6"

W = 960
MARGIN = 48
LABEL_W = 116
# Glyph coordinates are stored in units of GRID font units. Font units are
# 0.017 to 0.044 px at the sizes used here, so a coarser grid is invisible and
# shortens every number in the path data.
GRID = 4
NO_LIGS = {"calt": False, "liga": False, "dlig": False}

PANGRAM = "Sphinx of black quartz, judge my vow."
# Groups of easily confused glyphs. "rn" stays one cluster so it reads like "m".
LOOKALIKES = [["0", "O", "o"], ["1", "l", "I", "i", "|"], ["5", "S"],
              ["2", "Z"], ["8", "B"], ["rn", "m"], ["'", "`"]]
LIGATURES = [
    ["->", "=>", "<-", "<=", ">=", "==", "!=", "===", "<->", "<=>", "|>", "<|"],
    ["::", "...", "//", "/*", "*/", "~>", "??", ":=", "<!--", "-->", "</>"],
]

DIGITS = "0123456789"
GROUPS = {
    "Brackets": "()[]{}<>",
    "Operators": "+-*/=%^~|\\",
    "Punctuation": ".,:;!?\"'`",
    "Other": "#$&@_",
}
UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase


def luminance(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted([luminance(a), luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


class Face:
    def __init__(self, path, key):
        self.key = key
        self.tt = TTFont(path)
        self.upm = self.tt["head"].unitsPerEm
        self.order = self.tt.getGlyphOrder()
        self.glyphs = self.tt.getGlyphSet()
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(path)))

    def shape(self, text, features=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, features or {})
        return list(zip(buf.glyph_infos, buf.glyph_positions))

    def path(self, gid):
        pen = SVGPathPen(self.glyphs, lambda v: str(round(v / GRID)))
        self.glyphs[self.order[gid]].draw(pen)
        return pen.getCommands()


class Canvas:
    def __init__(self):
        self.defs = {}
        self.body = []

    def text(self, face, text, x, y, size, fill, features=None, tracking=0):
        """Draw text with its baseline at y. tracking is extra px between
        glyphs. Returns the advance in px."""
        scale = size / face.upm
        track = round(tracking / scale)
        pen = 0
        uses = []
        for info, pos in face.shape(text, features):
            gid_id = f"{face.key}{info.codepoint}"
            if gid_id not in self.defs:
                d = face.path(info.codepoint)
                self.defs[gid_id] = d
            if self.defs[gid_id]:
                ox = round((pen + pos.x_offset) / GRID)
                oy = round(pos.y_offset / GRID)
                attrs = f' x="{ox}"' if ox else ""
                attrs += f' y="{oy}"' if oy else ""
                uses.append(f'<use href="#{gid_id}"{attrs}/>')
            pen += pos.x_advance + track
        self.body.append(
            f'<g transform="translate({x:g} {y:g}) scale({scale * GRID:g} {-scale * GRID:g})" '
            f'fill="{fill}">{"".join(uses)}</g>')
        return pen * scale

    def rule(self, y):
        self.body.append(
            f'<rect x="{MARGIN}" y="{y:g}" width="{W - 2 * MARGIN}" height="1" fill="{RULE}"/>')

    def svg(self, height, title):
        defs = "".join(f'<path id="{k}" d="{d}"/>' for k, d in self.defs.items() if d)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" '
            f'width="{W}" height="{height}" role="img">'
            f"<title>{title}</title>"
            f'<rect width="{W}" height="{height}" rx="12" fill="{BG}"/>'
            f"<defs>{defs}</defs>{''.join(self.body)}</svg>\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default=os.path.expanduser("~/Library/Fonts"))
    ap.add_argument("--family", default="IosevkaHeiskr")
    ap.add_argument("--out", default="preview.svg")
    args = ap.parse_args()

    faces = {}
    for i, weight in enumerate(WEIGHTS):
        for slope in ("", "Italic"):
            name = weight + slope if weight != "Regular" or not slope else "Italic"
            path = os.path.join(args.fonts, f"{args.family}-{name}.ttf")
            faces[(weight, slope)] = Face(path, f"w{i}{'i' if slope else 'u'}")
    regular = faces[("Regular", "")]
    italic = faces[("Regular", "Italic")]
    bold = faces[("Bold", "")]

    # Every printable ASCII character except space must appear exactly once
    # in the character set rows.
    shown = UPPER + LOWER + DIGITS + "".join(GROUPS.values())
    printable = [chr(c) for c in range(0x21, 0x7F)]
    assert sorted(shown) == sorted(printable), set(printable) ^ set(shown)

    c = Canvas()
    y = MARGIN + 36
    c.text(bold, "Iosevka Heiskr", MARGIN, y, 44, FG)
    y += 30
    c.text(regular, "Humanist, single-storey, serifless. 548-unit width. "
           "9 weights, upright and italic.", MARGIN, y, 15, LABEL)
    y += 28
    c.rule(y)

    def label(text, ly, lx=MARGIN):
        c.text(regular, text, lx, ly, 14, LABEL)

    # Letters
    y += 54
    for name, face, chars in (("Upper", regular, UPPER),
                              ("Lower", regular, LOWER),
                              ("Italic", italic, LOWER),
                              ("Digits", regular, DIGITS)):
        label(name, y)
        c.text(face, chars, MARGIN + LABEL_W, y, 34, FG, NO_LIGS)
        y += 52

    y -= 14
    c.rule(y)

    # Symbols, two columns
    col2 = W // 2 + 8
    names = list(GROUPS)
    y += 50
    for left, right in zip(names[0::2], names[1::2]):
        for x, name in ((MARGIN, left), (col2, right)):
            label(name, y, x)
            c.text(regular, GROUPS[name], x + LABEL_W, y, 30, FG, NO_LIGS, tracking=9)
        y += 50

    y -= 16
    c.rule(y)

    # Lookalikes and ligatures
    def groups(items, ly, size, features, inner, gap):
        x = MARGIN + LABEL_W
        for group in items:
            for cluster in group:
                x += c.text(regular, cluster, x, ly, size, FG, features) + inner
            x += gap - inner

    y += 50
    label("Lookalikes", y)
    groups(LOOKALIKES, y, 30, NO_LIGS, 8, 34)
    y += 50
    label("Ligatures", y)
    for row in LIGATURES:
        groups([[lig] for lig in row], y, 26, None, 0, 22)
        y += 40

    y -= 18
    c.rule(y)

    # Weights: upright and italic pangram per weight
    y += 42
    sample_size = 17
    cell = regular.shape("0")[0][1].x_advance / regular.upm
    col_w = len(PANGRAM) * sample_size * cell
    x_up = MARGIN + LABEL_W
    x_it = W - MARGIN - col_w
    label("Upright", y, x_up)
    label("Italic", y, x_it)
    y += 30
    for weight in WEIGHTS:
        label(weight, y)
        c.text(faces[(weight, "")], PANGRAM, x_up, y, sample_size, FG)
        c.text(faces[(weight, "Italic")], PANGRAM, x_it, y, sample_size, FG)
        y += 29

    height = round(y - 29 + MARGIN)
    with open(args.out, "w") as f:
        f.write(c.svg(height, "Iosevka Heiskr specimen: all 94 visible ASCII "
                      "characters, italic lowercase, lookalikes, ligatures, "
                      "and nine weights in upright and italic"))

    if shutil.which("svgo"):
        subprocess.run(["svgo", "-q", args.out, "-o", args.out], check=True)
    else:
        print("svgo not found, skipping minification")

    print(f"{args.out}: {W}x{height}, {os.path.getsize(args.out) // 1024} KB, "
          f"{len(c.defs)} glyphs")
    print(f"contrast FG/BG {contrast(FG, BG):.2f}:1, "
          f"LABEL/BG {contrast(LABEL, BG):.2f}:1, BG luminance {luminance(BG):.2f}")


if __name__ == "__main__":
    main()
