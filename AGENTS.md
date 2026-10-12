# zmk-config — Kurt's Corne keyboard

ZMK firmware config for a wireless Corne (nice!nano v2, both halves), plus a
generated visual of its layers. Firmware builds on GitHub Actions on push
(`build.yaml`); flash the two `.uf2` files from the run's artifact.

## Layout

- `config/corne.keymap` — the source of truth. Six layers: **Kinesis** (base,
  Kinesis Advantage360 letter block), **Num/Nav** (hold ⌦), **Symbols** (hold ⏎;
  the Num layer with shift already applied, nav keys unchanged), **Fn** (hold `\`,
  top right), **Steno** (both inner thumbs together toggles), **Arrows** (both
  outer thumbs together toggles, locks on).
- Each layer sets the underglow colour through a macro: white base, blue Num/Nav,
  orange Symbols, purple Fn, green Steno, cyan Arrows.
- `config/corne.conf` — NKRO is on (`CONFIG_ZMK_HID_REPORT_TYPE_NKRO=y`) because
  steno chords exceed six keys.
- The Steno layer sends the QWERTY letters Plover's "Keyboard" machine expects.
  Vowels are on the outer two thumbs per hand: C V = A O, N M = E U. The left
  pinky column is unused; both S keys sit one column in.

## Layer visual

`./draw-keymap [--open]` regenerates, from the keymap:

- `docs/corne-keymap.svg` — all six layers, dark theme, two columns
- `docs/corne-steno.svg` — the Steno layer alone, larger, as a practice card
- `docs/corne-keymap.html` — interactive: one layer at a time, a tab per layer
  (`--open` opens this one)

Pipeline: `keymap parse` (keymap-drawer, run through `uvx`) → `docs/keymap_style.py`
→ `keymap draw` with `docs/keymap-drawer.config.yaml` → a `sed` pass in
`draw-keymap` that adds the "how to reach this layer" hint beside each title.

- `docs/keymap_style.py` owns the **content**: Mac symbols, readable names for the
  macros, base letters ghosted under pass-through keys (`type: thru`), dead keys
  (`off`), held layer keys (`held`), and the steno legends — steno key as the main
  legend, QWERTY letter as the small top legend, coloured by group (`sl` left
  consonants, `sr` right, `sv` vowels, `sx` star, `sn` number bar).
- `docs/keymap-drawer.config.yaml` owns the **look**: sizes and all CSS
  (`svg_extra_style`). Layer colours are keyed on `.layer-<Name>` classes.
- `docs/corne-keymap.yaml` is generated; don't hand-edit it.
- `docs/keymap_page.py` builds the page: legends from the YAML, key positions
  scraped from the drawn SVG, and the "doors" (hold keys and combos that lead to
  another layer) worked out from both. Layer colours, LED names and notes are
  dicts at the top. `docs/keymap-page.template.html` is the page itself (CSS and
  JS inline, no dependencies); `docs/corne-keymap.html` is generated.
- On the page, each tab's mini board lights the keys that reach that layer, door
  keys on the board are outlined in the destination's colour and clickable, and
  hovering a tab highlights its way in from the layer on show. `#steno` etc. in
  the URL opens a layer directly.

To check a change visually, screenshot the SVG with headless Chrome and look at it:

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --hide-scrollbars --window-size=1944,1139 --screenshot=/tmp/corne.png \
  "file://$PWD/docs/corne-keymap.svg"
```

## Live viewer app

`./viewer/build [--open]` compiles `viewer/CorneLayers.swift` into
`viewer/dist/Corne Layers.app` (git-ignored): a floating window that hosts
`docs/corne-keymap.html` and feeds it what the keyboard sends.

- The app reads the Corne's raw HID reports through `IOHIDManager` (Input
  Monitoring permission). It only listens, so nothing is intercepted. It keeps
  devices whose product name contains "Corne" (`--device NAME` to change,
  `--log` to print every HID value).
- The Mac can't see layers, so every layer macro in the keymap also taps a
  consumer key macOS ignores (`SIG_*` defines at the top of `corne.keymap`:
  Media Select TV/VCR/Tuner/Tape/Cable/Satellite). A new layer needs a `SIG_`
  define, a tap in its macro, and an entry in `CONSUMER` in `keymap_page.py`.
- Signals have to be consumer keys: with NKRO on, ZMK's keyboard report stops
  at keypad `=`, so F13 and up can't be sent.
- `keymap_page.py` parses the keymap's bindings into per-layer HID usages
  (`codes`), shift-implied positions (`shifted`) and the layer `signal`; the
  page's `window.live.hid(page, usage, value)` does the rest. Rebuild the app
  after a keymap change, since it bundles a copy of the page.
- Karabiner-Elements is installed on Kurt's Mac. If it grabs the Corne, the app
  sees nothing from it: turn off "Modify events" for the Corne in Karabiner.
- Not yet verified on hardware (2026-10-12): that the signals arrive and that
  macOS ignores them, and that keys still show while Plover is capturing.

## Design state (2026-10-12)

First designed pass is done and was checked layer by layer. Known rough edges and
ideas not yet done:

- The layer hints live in a `sed` block in `draw-keymap`, separate from the rest
  of the content; a new or renamed layer needs a line there and CSS for its colour.
- The steno card and full sheet share one stylesheet; the card only overrides
  key size and column count.
- The interactive page (first pass 2026-10-12) has its own stylesheet and its
  own layer colour table, so a layer colour now lives in three places: the SVG
  CSS, the `sed` hints, and `LEDS` in `keymap_page.py`.

## Related

- Kurt also has a Naya Create configured for steno; the plan is to make the Corne
  the single steno board.
- Steno practice is Plover + Typey Type.
