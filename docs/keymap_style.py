#!/usr/bin/env python3
"""Turn keymap-drawer's parsed Corne keymap into a friendlier one.

Reads the YAML from `keymap parse` on stdin and writes YAML for `keymap draw`:
Mac symbols, readable names for the custom macros, base-layer letters ghosted
under pass-through keys, held layer keys marked, and real steno keys on the
Steno layer with the QWERTY letter Plover listens for above each one.
"""
import sys

import yaml

BASE = "Kinesis"

SYMBOLS = {
    "TAB": "⇥", "ESC": "esc", "LSHFT": "⇧", "RSHFT": "⇧", "LCTRL": "ctrl",
    "LGUI": "⌘", "LALT": "⌥", "BSPC": "⌫", "DEL": "⌦", "ENTER": "⏎",
    "SPACE": "␣", "LEFT": "←", "RIGHT": "→", "UP": "↑", "DOWN": "↓",
    "PG UP": "pg↑", "PG DN": "pg↓", "HOME": "home", "END": "end",
    "CAPS": "caps", "BT CLR": "BT clear", "OUT TOG": "USB BT", "RGB TOG": "RGB",
    "&bootloader": "boot", "&sys_reset": "reset", "&studio_unlock": "studio",
    "&rgb_reset": "RGB fix",
    "Ctl+UP": "mission control", "Ctl+LEFT": "desk ←", "Ctl+RIGHT": "desk →",
    "&num_c": "Num", "&num_cn": "Num", "&sym_c": "Sym", "&sym_cn": "Sym",
    "&row_c": "123", "&srow_c": "!@#", "&fn_c": "Fn", "&fn_cn": "Fn",
    "&steno_on": "Steno", "&steno_off": "exit", "&nav_on": "Arrows", "&nav_off": "exit",
    "&rows_c": "Rows", "Hyper+D": "dictate", "&lsft_gate": "⇧",
    # the Rows number row (mod-morphs that drop shift): show the plain key
    **{f"&us_{k}": v for k, v in {**{f"N{i}": str(i) for i in range(10)}, "EQUAL": "=", "MINUS": "-"}.items()},
}

# helper layers that are never seen on their own (left shift holds LGate so esc opens Rows)
HIDDEN = {"LGate"}

# combos that hold a layer for as long as their keys are down, rather than toggle it
HOLD_COMBOS = {"&rows_c"}

# QWERTY letter Plover's keyboard machine expects -> (steno key, colour group)
STENO = {
    "Q": ("S", "sl"), "A": ("S", "sl"), "W": ("T", "sl"), "S": ("K", "sl"),
    "E": ("P", "sl"), "D": ("W", "sl"), "R": ("H", "sl"), "F": ("R", "sl"),
    "T": ("✱", "sx"), "G": ("✱", "sx"), "Y": ("✱", "sx"), "H": ("✱", "sx"),
    "U": ("F", "sr"), "J": ("R", "sr"), "I": ("P", "sr"), "K": ("B", "sr"),
    "O": ("L", "sr"), "L": ("G", "sr"), "P": ("T", "sr"), ";": ("S", "sr"),
    "[": ("D", "sr"), "'": ("Z", "sr"),
    "C": ("A", "sv"), "V": ("O", "sv"), "N": ("E", "sv"), "M": ("U", "sv"),
}

# key positions that are physically held down while a layer is showing
HELD = {"Num/Nav": [38], "Symbols": [39], "Fn": [11], "NumRow": [38, 40], "SymRow": [39, 37],
        "Rows": [12, 24, 23, 35]}   # either edge pair


def as_dict(key):
    return dict(key) if isinstance(key, dict) else {"t": "" if key is None else str(key)}


def pretty(key):
    # Bluetooth profiles: ZMK counts from 0, people count from 1
    if key.get("t") == "BT" and str(key.get("h", "")).isdigit():
        key["t"] = f"BT {int(key.pop('h')) + 1}"
    for field in ("t", "h", "s"):
        if field in key:
            key[field] = SYMBOLS.get(str(key[field]), key[field])
    return key


def main():
    data = yaml.safe_load(sys.stdin)
    layers = {name: [as_dict(k) for row in rows for k in row] for name, rows in data["layers"].items()
              if name not in HIDDEN}
    base = [pretty(dict(k)) for k in layers[BASE]]

    for name, keys in layers.items():
        for pos, key in enumerate(keys):
            if key.get("type") == "trans":
                keys[pos] = {"t": base[pos].get("t", ""), "type": "thru"}
            elif name == "Steno":
                letter = key.get("t", "")
                if letter in STENO:
                    steno, group = STENO[letter]
                    keys[pos] = {"t": steno, "s": letter.lower(), "type": group}
                elif letter:
                    keys[pos] = {"t": "#", "s": letter, "type": "sn"}
                else:
                    keys[pos] = {"t": "", "type": "off"}
            elif not key.get("t") and not key.get("h"):
                keys[pos] = {"t": "", "type": "off"}
            else:
                pretty(key)
        for pos in HELD.get(name, []):
            keys[pos] = {"t": base[pos].get("t", ""), "h": "held", "type": "held"}

    data["layers"] = layers
    for combo in data.get("combos", []):
        if not str(combo["k"]).startswith("&"):
            # two keys that type something together: a small pill between them
            combo.update(k=SYMBOLS.get(combo["k"], combo["k"]), type="chord", w=26, h=22)
            continue
        arrows = combo["k"] in ("&nav_on", "&nav_off")
        if combo["k"] in HOLD_COMBOS:
            combo["type"] = "hold"
        combo["k"] = SYMBOLS.get(combo["k"], combo["k"])
        # inner-thumb combo sits above the thumbs, the others below their keys
        combo["a"] = "top" if combo["p"] == [38, 39] else "bottom"
        combo["o"] = 0.35
        if arrows:
            combo["type"] = "nav"
    yaml.safe_dump(data, sys.stdout, allow_unicode=True, sort_keys=False, width=200)


if __name__ == "__main__":
    main()
