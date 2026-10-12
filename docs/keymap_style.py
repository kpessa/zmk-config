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
}

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
HELD = {"Num/Nav": [38], "Symbols": [39], "Fn": [11], "NumRow": [38, 40], "SymRow": [39, 37]}


def as_dict(key):
    return dict(key) if isinstance(key, dict) else {"t": "" if key is None else str(key)}


def pretty(key):
    # the Command thumb: Command is the point, dictation is what a lone tap does
    if key.get("t") == "Hyper+D" and key.get("h") == "LGUI":
        key.clear()
        key.update({"t": "⌘", "s": "dictate"})
    # Bluetooth profiles: ZMK counts from 0, people count from 1
    if key.get("t") == "BT" and str(key.get("h", "")).isdigit():
        key["t"] = f"BT {int(key.pop('h')) + 1}"
    for field in ("t", "h", "s"):
        if field in key:
            key[field] = SYMBOLS.get(str(key[field]), key[field])
    return key


def main():
    data = yaml.safe_load(sys.stdin)
    layers = {name: [as_dict(k) for row in rows for k in row] for name, rows in data["layers"].items()}
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
        combo["k"] = SYMBOLS.get(combo["k"], combo["k"])
        # inner-thumb combo sits above the thumbs, outer-thumb combo below
        combo["a"] = "top" if combo["p"] == [38, 39] else "bottom"
        combo["o"] = 0.35
        if combo["p"] == [36, 41]:
            combo["type"] = "nav"
    yaml.safe_dump(data, sys.stdout, allow_unicode=True, sort_keys=False, width=200)


if __name__ == "__main__":
    main()
