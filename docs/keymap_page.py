#!/usr/bin/env python3
"""Build the interactive layer page, docs/corne-keymap.html.

Usage: keymap_page.py KEYMAP_YAML KEYMAP_SVG TEMPLATE KEYMAP > page.html

Takes the styled YAML from keymap_style.py for the legends and the drawn SVG for
the physical key positions, works out which keys lead to which layer, and drops
it all into the template as JSON.

For the viewer app (viewer/) it also reads the keymap itself: the HID usage each
key sends on each layer, and the consumer key each layer taps as its signal.
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
    # no colour of its own: the LEDs keep whichever thumb's colour came last
    "Row": ("#e6c84f", "Blue or orange"),
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

# ZMK key name -> HID keyboard usage, for the keys this keymap uses
USAGE = {
    **{chr(65 + i): 4 + i for i in range(26)},
    **{f"N{(i + 1) % 10}": 30 + i for i in range(10)},
    **{f"F{i + 1}": 58 + i for i in range(12)},
    "ENTER": 40, "ESC": 41, "BSPC": 42, "TAB": 43, "SPACE": 44, "MINUS": 45, "EQUAL": 46,
    "LBKT": 47, "RBKT": 48, "BSLH": 49, "SEMI": 51, "SQT": 52, "GRAVE": 53, "COMMA": 54,
    "DOT": 55, "FSLH": 56, "CAPS": 57, "HOME": 74, "PG_UP": 75, "DEL": 76, "END": 77,
    "PG_DN": 78, "RIGHT": 79, "LEFT": 80, "DOWN": 81, "UP": 82,
    "LCTRL": 224, "LSHFT": 225, "LALT": 226, "LGUI": 227,
    "RCTRL": 228, "RSHFT": 229, "RALT": 230, "RGUI": 231,
}
# keys ZMK sends as shift + another key
WITH_SHIFT = {
    "EXCL": "N1", "AT": "N2", "HASH": "N3", "DLLR": "N4", "PRCNT": "N5", "CARET": "N6",
    "AMPS": "N7", "STAR": "N8", "LPAR": "N9", "RPAR": "N0", "PLUS": "EQUAL", "UNDER": "MINUS",
    "TILDE": "GRAVE", "LBRC": "LBKT", "RBRC": "RBKT", "PIPE": "BSLH", "COLON": "SEMI",
    "DQT": "SQT", "LT": "COMMA", "GT": "DOT", "QMARK": "FSLH",
}
# consumer keys used as layer signals -> HID consumer usage
CONSUMER = {
    "C_MEDIA_TV": 0x89, "C_MEDIA_VCR": 0x92, "C_MEDIA_TUNER": 0x93,
    "C_MEDIA_TAPE": 0x96, "C_MEDIA_CABLE": 0x97, "C_MEDIA_SATELLITE": 0x98,
}

KEY = re.compile(
    r'<g transform="translate\(([-\d.]+), ([-\d.]+)\)(?: rotate\(([-\d.]+)\))?" class="key keypos-(\d+)">\s*'
    r'<rect[^>]*width="([\d.]+)" height="([\d.]+)"'
)


def geometry(svg):
    keys = {}
    for x, y, r, pos, w, h in KEY.findall(svg):
        keys.setdefault(int(pos), {"x": float(x), "y": float(y), "r": float(r or 0), "w": float(w), "h": float(h)})
    return [keys[pos] for pos in sorted(keys)]


def live(keymap):
    """Per layer: the usages each position sends, the shift-implied positions, the signal."""
    defines = dict(re.findall(r"^#define (\w+) (\w+)$", keymap, re.M))
    signals = {int(n): CONSUMER[defines["SIG_" + name]] for name, n in defines.items()
               if n.isdigit() and defines.get("SIG_" + name) in CONSUMER}
    out = []
    for index, block in enumerate(re.findall(r"bindings\s*=\s*<(.*?)>;", keymap.split("keymap {")[-1], re.S)):
        codes, shifted = [], []
        for pos, binding in enumerate(block.split("&")[1:]):
            behaviour, *params = binding.split()
            if behaviour == "trans" and out:
                codes.append(out[0]["codes"][pos])
                continue
            if any(p in WITH_SHIFT for p in params):
                shifted.append(pos)
            codes.append([USAGE[WITH_SHIFT.get(p, p)] for p in params if WITH_SHIFT.get(p, p) in USAGE])
        out.append({"codes": codes, "shifted": shifted, "signal": signals.get(index)})
    return out


def conditionals(keymap, names):
    """Layers that switch on while a set of other layers is held: [{if: [names], then: name}]."""
    defines = dict(re.findall(r"^#define (\w+) (\d+)$", keymap, re.M))
    rules = re.findall(r"if-layers\s*=\s*<([^>]*)>;\s*then-layer\s*=\s*<(\w+)>;", keymap)
    return [{"if": [names[int(defines[n])] for n in needs.split()], "then": names[int(defines[then])]}
            for needs, then in rules]


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
    keymap_yaml, keymap_svg, template, keymap = sys.argv[1:5]
    data = yaml.safe_load(open(keymap_yaml))
    layers, combos = data["layers"], data.get("combos", [])
    for keys in layers.values():
        for key in keys:
            if not key.get("type") and str(key.get("t")) in SHIFTED:
                key.setdefault("s", SHIFTED[str(key["t"])])
    all_doors = {name: doors(name, keys, combos, layers) for name, keys in layers.items()}

    out = []
    wiring = live(open(keymap).read())
    for (name, keys), wired in zip(layers.items(), wiring):
        colour, led = LEDS.get(name, ("#8d95a3", "Grey"))
        layer = {
            "name": name, "colour": colour, "led": led, "note": NOTES.get(name, ""),
            "keys": keys, "doors": all_doors[name], "kind": "base", "how": "", "enter": [],
            **wired,
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

    # a conditional layer is held like its parts, and each part's key is a door to it
    byname = {layer["name"]: layer for layer in out}
    rules = conditionals(open(keymap).read(), list(layers))
    for rule in rules:
        then, parts = byname[rule["then"]], [byname[n] for n in rule["if"]]
        then.update(kind="hold", how=" and ".join(p["how"] for p in parts),
                    enter=[pos for p in parts for pos in p["enter"]])
        for part in parts:
            for other in parts:
                if other is not part:
                    part["doors"].append({"to": then["name"], "kind": "hold", "p": other["enter"]})

    page = {"base": BASE, "conditional": rules, "geometry": geometry(open(keymap_svg).read()), "layers": out}
    blob = json.dumps(page, ensure_ascii=False).replace("</", "<\\/")
    sys.stdout.write(open(template).read().replace("__KEYMAP_DATA__", blob))


if __name__ == "__main__":
    main()
