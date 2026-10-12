#!/usr/bin/env python3
"""Build the interactive layer page, docs/corne-keymap.html.

Usage: keymap_page.py KEYMAP_YAML KEYMAP_SVG TEMPLATE > page.html

Takes the styled YAML from keymap_style.py for the legends and the drawn SVG for
the physical key positions, works out which keys lead to which layer, and drops
it all into the template as JSON.
"""
import json
import re
import sys

import yaml

BASE = "Kinesis"

# layer -> (underglow colour, its name in words)
LEDS = {
    "Kinesis": ("#f2f3f5", "White"),
    "Num/Nav": ("#6f9bff", "Blue"),
    "Symbols": ("#ffa04d", "Orange"),
    "Fn": ("#b98aff", "Purple"),
    "Steno": ("#4fd684", "Green"),
    "Arrows": ("#3fd0dc", "Cyan"),
}

NOTES = {
    "Steno": "The small letter on each key is the one Plover sees.",
    "Arrows": "Typing still works here.",
}

# hold legend (from keymap_style.SYMBOLS) -> layer it holds
HOLDS = {"Num": "Num/Nav", "Sym": "Symbols", "Fn": "Fn"}

# what a key sends with shift held, shown small above its legend
SHIFTED = dict(zip("1234567890-=[]`;',./\\", "!@#$%^&*()_+{}~:\"<>?|"))

# combo key positions -> how to say them
COMBO_KEYS = {(38, 39): "both inner thumbs", (37, 40): "both middle thumbs", (36, 41): "both outer thumbs"}

KEY = re.compile(
    r'<g transform="translate\(([-\d.]+), ([-\d.]+)\)(?: rotate\(([-\d.]+)\))?" class="key keypos-(\d+)">\s*'
    r'<rect[^>]*width="([\d.]+)" height="([\d.]+)"'
)


def geometry(svg):
    keys = {}
    for x, y, r, pos, w, h in KEY.findall(svg):
        keys.setdefault(int(pos), {"x": float(x), "y": float(y), "r": float(r or 0), "w": float(w), "h": float(h)})
    return [keys[pos] for pos in sorted(keys)]


def doors(name, keys, combos, layers):
    """Keys on this layer that take you to another one."""
    found = {}
    for pos, key in enumerate(keys):
        to = HOLDS.get(key.get("h"))
        if to:
            found.setdefault(to, {"to": to, "kind": "hold", "p": []})["p"].append(pos)
    out = list(found.values())
    for combo in combos:
        if name not in combo.get("l", []):
            continue
        to = combo["k"] if combo["k"] in layers else BASE
        out.append({"to": to, "kind": "combo", "p": combo["p"], "a": combo.get("a", "top")})
    return out


def main():
    keymap_yaml, keymap_svg, template = sys.argv[1:4]
    data = yaml.safe_load(open(keymap_yaml))
    layers, combos = data["layers"], data.get("combos", [])
    for keys in layers.values():
        for key in keys:
            if not key.get("type") and str(key.get("t")) in SHIFTED:
                key.setdefault("s", SHIFTED[str(key["t"])])
    all_doors = {name: doors(name, keys, combos, layers) for name, keys in layers.items()}

    out = []
    for name, keys in layers.items():
        colour, led = LEDS.get(name, ("#8d95a3", "Grey"))
        layer = {
            "name": name, "colour": colour, "led": led, "note": NOTES.get(name, ""),
            "keys": keys, "doors": all_doors[name], "kind": "base", "how": "", "enter": [],
        }
        # how you get here from the base layer
        for door in all_doors[BASE]:
            if door["to"] != name or name == BASE:
                continue
            layer["enter"] = door["p"]
            if door["kind"] == "hold":
                layer["kind"] = "hold"
                layer["how"] = " or ".join(layers[BASE][p]["t"] for p in door["p"])
            else:
                layer["kind"] = "toggle"
                layer["how"] = COMBO_KEYS.get(tuple(sorted(door["p"])), "the linked keys")
        out.append(layer)

    page = {"base": BASE, "geometry": geometry(open(keymap_svg).read()), "layers": out}
    blob = json.dumps(page, ensure_ascii=False).replace("</", "<\\/")
    sys.stdout.write(open(template).read().replace("__KEYMAP_DATA__", blob))


if __name__ == "__main__":
    main()
