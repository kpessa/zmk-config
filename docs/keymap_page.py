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
    "NumRow": ("#e6c84f", "Yellow"),
    "SymRow": ("#ff7eb6", "Pink"),
}

NOTES = {
    "Steno": "The small letter on each key is the one Plover sees.",
    "Arrows": "Typing still works here.",
}

# hold legend (from keymap_style.SYMBOLS) -> layer it holds
HOLDS = {"Num": "Num/Nav", "Sym": "Symbols", "Fn": "Fn", "123": "NumRow", "!@#": "SymRow"}

# what a key sends with shift held, shown small above its legend
SHIFTED = dict(zip("1234567890-=[]`;',./\\", "!@#$%^&*()_+{}~:\"<>?|"))

# combo key positions -> how to say them
COMBO_KEYS = {(38, 39): "both inner thumbs", (37, 40): "both middle thumbs", (36, 41): "both outer thumbs",
              (22, 33, 35): "; . and right shift"}

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
# modifier wrappers such as LC(...): letter -> left-hand usage (right-hand is +4)
MODIFIERS = {"C": 224, "S": 225, "A": 226, "G": 227}
# consumer keys used as layer signals -> HID consumer usage
CONSUMER = {
    "C_MEDIA_TV": 0x89, "C_MEDIA_VCR": 0x92, "C_MEDIA_TUNER": 0x93,
    "C_MEDIA_TAPE": 0x96, "C_MEDIA_CABLE": 0x97, "C_MEDIA_SATELLITE": 0x98,
    "C_MEDIA_GAMES": 0x8F, "C_MEDIA_CD": 0x91,
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


def unwrap(param):
    """LC(LS(X)) -> ([ctrl, shift], "X"); EXCL -> ([shift], "N1")."""
    mods = []
    while m := re.fullmatch(r"([LR])([CSAG])\((.+)\)", param):
        mods.append(MODIFIERS[m[2]] + (4 if m[1] == "R" else 0))
        param = m[3]
    if param in WITH_SHIFT:
        mods.append(MODIFIERS["S"])
        param = WITH_SHIFT[param]
    return mods, param


def live(keymap):
    """Per layer: the usages each position sends, the keys sent with modifiers, the signal.

    `combos` are positions that send a key together with modifiers of their own
    ({pos, mods, key}); the page matches those first so it lights that one key
    rather than the key and each modifier.
    """
    defines = dict(re.findall(r"^#define (\w+) (\w+)$", keymap, re.M))
    signals = {int(n): CONSUMER[defines["SIG_" + name]] for name, n in defines.items()
               if n.isdigit() and defines.get("SIG_" + name) in CONSUMER}
    out = []
    for index, block in enumerate(re.findall(r"bindings\s*=\s*<(.*?)>;", keymap.split("keymap {")[-1], re.S)):
        codes, combos, own = [], [], []
        for pos, binding in enumerate(block.split("&")[1:]):
            behaviour, *params = binding.split()
            codes.append([])
            if behaviour == "trans" and out:
                codes[pos] = list(out[0]["codes"][pos])
                combos += [c for c in out[0]["combos"] if c["pos"] == pos]
                continue
            for mods, name in map(unwrap, params):
                if name not in USAGE:
                    continue
                if mods:
                    own.append({"pos": pos, "mods": mods, "key": USAGE[name]})
                else:
                    codes[pos].append(USAGE[name])
        # fallback for a combo whose modifiers went unseen: its key alone, when no other key sends it
        for combo in own:
            if not any(combo["key"] in sent for sent in codes):
                codes[combo["pos"]].append(combo["key"])
        out.append({"codes": codes, "combos": combos + own, "signal": signals.get(index)})
    return out


CHORD = re.compile(r"bindings\s*=\s*<&kp\s+([^>]+?)\s*>;\s*key-positions\s*=\s*<([\d\s]+)>;\s*layers\s*=\s*<([^>]+)>;")


def chords(keymap, names, drawn):
    """Combos that type a key rather than change layer, per layer name:
    [{p: positions, t: legend, key: usage, mods: [usages]}]."""
    defines = dict(re.findall(r"^#define (\w+) (\d+)$", keymap, re.M))
    legend = {tuple(c["p"]): str(c["k"]) for c in drawn if c.get("type") == "chord"}
    out = {name: [] for name in names}
    for param, positions, on in CHORD.findall(keymap.split("combos {")[-1].split("keymap {")[0]):
        mods, key = unwrap(param)
        p = [int(n) for n in positions.split()]
        if key not in USAGE:
            continue
        for layer in on.split():
            out[names[int(defines[layer])]].append({"p": p, "t": legend.get(tuple(p), param), "key": USAGE[key], "mods": mods})
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
        if name not in combo.get("l", []) or combo.get("type") == "chord":
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
    typed = chords(open(keymap).read(), list(layers), combos)
    for (name, keys), wired in zip(layers.items(), wiring):
        colour, led = LEDS.get(name, ("#8d95a3", "Grey"))
        layer = {
            "name": name, "colour": colour, "led": led, "note": NOTES.get(name, ""),
            "keys": keys, "doors": all_doors[name], "kind": "base", "how": "", "enter": [],
            "chords": typed[name],
            **wired,
        }
        # how you get here from the base layer
        for door in all_doors[BASE]:
            if door["to"] != name or name == BASE:
                continue
            if door["kind"] == "hold":
                layer["enter"] = door["p"]
                layer["kind"] = "hold"
                layer["how"] = " or ".join(layers[BASE][p]["t"] for p in door["p"])
            else:
                # a layer can have more than one combo that toggles it
                said = COMBO_KEYS.get(tuple(sorted(door["p"])), "the linked keys")
                again = layer["kind"] == "toggle"
                layer["how"] = f'{layer["how"]}, or {said}' if again else said
                layer["enter"] = layer["enter"] + door["p"] if again else door["p"]
                layer["kind"] = "toggle"
        out.append(layer)

    # layers reached from a held layer rather than from the base: hold one key, then another
    for layer in out:
        if layer["kind"] != "base" or layer["name"] == BASE:
            continue
        for via in out:
            door = next((d for d in via["doors"] if d["to"] == layer["name"] and d["kind"] == "hold"), None)
            if door and via["kind"] == "hold":
                then = " or ".join(layers[via["name"]][p]["t"] for p in door["p"])
                layer.update(kind="hold", how=f'{via["how"]}, then {then}', enter=via["enter"] + door["p"])
                break

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
