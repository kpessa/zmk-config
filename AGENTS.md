# zmk-config — Kurt's Corne keyboard

ZMK firmware config for a wireless Corne (nice!nano v2, both halves), plus a
generated visual of its layers. Firmware builds on GitHub Actions on push
(`build.yaml`); flash the two `.uf2` files from the run's artifact.

## Layout

- `config/corne.keymap` — the source of truth. Eight layers: **Kinesis** (base,
  Kinesis Advantage360 letter block), **Num/Nav** (hold ⌦; numpad under the right
  hand reading 1 2 3 from the top, arrow cluster under the left), **Symbols**
  (hold ⏎; right hand is the Num layer with shift already applied, left hand is
  the bracket pairs `[ ]` / `( )` / `{ }` stacked on the E/R, D/F, C/V columns), **NumRow**
  (hold ⌦, then also ␣: the classic number row across the top), **SymRow** (hold
  ⏎, then also ⌫: that row's symbols), **Fn** (hold `\`,
  top right), **Steno** (both inner thumbs together toggles), **Arrows** (both
  outer thumbs together toggles, locks on).
- Each layer sets the underglow colour through a macro: white base, blue Num/Nav,
  orange Symbols, yellow NumRow, pink SymRow, purple Fn, green Steno, cyan Arrows.
- Both inner thumbs pressed together is the Steno toggle, so nothing else should
  use ⌦ + ⏎ (a both-thumbs number row was tried on 2026-10-12 and collided).
- Parentheses are also home-row combos on the base and Arrows layers: D + F is `(`,
  J + K is `)` (added 2026-10-13, after a typing test showed several seconds lost at
  each parenthesis; `(` usually follows a space, and space and the Symbols hold are
  both on the right thumb). `require-prior-idle-ms` keeps a fast d-f or j-k roll in a
  word from firing them; raise it if they misfire, lower it if they fail to fire.
  A + S is `!` and L + ; is `-` the same way (Kurt's choice, 2026-10-13), with a
  shorter `timeout-ms` because "as" is a common roll; that pair is the one to watch
  for misfires.
- F + G is left arrow and H + J is right arrow, the same kind of combo (Kurt uses
  those two a lot, 2026-10-13). On the Arrows layer the viewer lights the real arrow
  key for ← / →, since it can't tell which was pressed.
- **Rows** is a ninth layer (Kurt's idea, 2026-10-13; red LEDs; signal Media Select
  Program Guide, `C_MEDIA_GUIDE`): the number row on top with each number's symbol on
  the home row under it, as on a full keyboard. It is held with a two-key combo on
  either edge: esc + left shift, or ' + right shift (`rows_c`, a hold macro bound to
  a combo, which ZMK releases when either key comes up). `+` and `_` sit under the
  left and right pair, so each needs the other edge held. The drawing tools mark such
  a combo `type: hold` (`HOLD_COMBOS` in `keymap_style.py`). NumRow and SymRow are
  still there.
  Since 2026-10-18 the left pair also works in sequence: hold left shift, then esc
  (Kurt found the together-only combo hard to hit). Left shift is `lsft_gate`, a
  macro that holds LSHFT and a hidden `LGate` layer whose only key is esc → `rows_c`.
  Because shift is still down, the Rows number row uses `us_*` mod-morphs that drop
  shift, so it types 1, not !. `LGate` is last in the keymap and dropped from the
  drawings (`HIDDEN` in `keymap_style.py`). The right pair stays together-only:
  right shift then ' is how a " gets typed. Trade-off: shift-then-ctrl (esc held)
  now opens Rows; press ctrl first for Ctrl+Shift shortcuts.
  Also since 2026-10-18: hold Tab (top left) for Rows, mirroring Fn on the top right
  (`ltrows`, same balanced hold-tap timing as Fn). With Tab held, both `+` and `_` are
  reachable; `=` sits under Tab, so it needs one of the edge pairs.
- Arrows also toggles with ; . and right shift together, the keys under its up, left
  and right arrows (Kurt's idea, 2026-10-13), as well as both outer thumbs.
  The drawing tools call a combo that types something a "chord" (`type: chord` in the
  YAML, `chords` in the page data), as opposed to one that changes layer.
- Home row mods are a planned later step (Kurt agreed 2026-10-12: after the
  numpad settles, additive, with opposite-hand and prior-idle settings). If they
  stick, the esc/ctrl key's hold is the candidate for a pinky-held symbol row.
- Mac shortcuts: the ⌘ thumb is plain Command. It used to be tap = dictation, but
  Kurt kept setting dictation off when reaching for ⌫ (2026-10-18), so dictation
  (Ctrl+Opt+Shift+Cmd+D, his macOS shortcut) moved to Fn + G. Karabiner ignores the
  Corne, so its own tap-⌘-for-dictation rule only affects the other keyboards. The Symbols layer's far left has
  Mission Control (W) over desktop left / right (A, S), sent as Ctrl+arrows.
- `config/corne.conf` — NKRO is on (`CONFIG_ZMK_HID_REPORT_TYPE_NKRO=y`) because
  steno chords exceed six keys.
- The Steno layer sends the QWERTY letters Plover's "Keyboard" machine expects.
  Vowels are on the outer two thumbs per hand: C V = A O, N M = E U. The left
  pinky column is unused; both S keys sit one column in.

## Layer visual

`./draw-keymap [--open]` regenerates, from the keymap:

- `docs/corne-keymap.svg` — all eight layers, dark theme, two columns
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
`viewer/dist/Corne Layers.app` (git-ignored): a window that hosts
`docs/corne-keymap.html` and feeds it what the keyboard sends.

- The window is an ordinary one (minimisable, on one desktop, not on top) with a
  mini player: the button at the right of the title bar, or Window › Mini Player
  (⇧⌘M), shrinks it to the board and the layer's name, plus the stroke and word
  on Steno (no paper tape). The mini player floats over other apps unless
  Window › Keep Mini Player on Top is off. Each mode remembers its own size and
  place. The page's side of it is `body.mini` and `window.live.mini(on)`. The
  Naya app in `~/code/naya-layers` has the same window code.

- The app reads the Corne's raw HID reports through `IOHIDManager` (Input
  Monitoring permission). It only listens, so nothing is intercepted. It keeps
  devices whose product name contains "Corne" (`--device NAME` to change,
  `--log` to print every HID value).
- The Mac can't see layers, so every layer macro in the keymap also sends a
  consumer key macOS ignores (`SIG_*` defines at the top of `corne.keymap`:
  Media Select TV/VCR/Tuner/Tape/Cable/Satellite/Games/CD). Held layers keep theirs down
  while held; locked layers and the way back to base tap theirs. The page works
  out the layer from which are down (the newest held one wins). It also handles
  ZMK `conditional_layers`, though the keymap has none at the moment. A new layer needs a `SIG_`
  define, its macro sending it, and an entry in `CONSUMER` in `keymap_page.py`.
- Signals have to be consumer keys: with NKRO on, ZMK's keyboard report stops
  at keypad `=`, so F13 and up can't be sent.
- `keymap_page.py` parses the keymap's bindings into per-layer HID usages
  (`codes`) and the layer `signal`; the
  page's `window.live.hid(page, usage, value)` does the rest. Keys that send
  their own modifiers (`!`, `LC(LEFT)`, the dictation tap) are listed per layer
  as `combos` so the page lights that one key and not the modifiers. Rebuild the app
  after a keymap change, since it bundles a copy of the page.
- The app switches Plover with the Steno layer, so chords work without touching
  Plover: `Plover -s plover_send_command resume` on entering Steno, `suspend` on
  leaving and at launch, starting Plover first if needed (`--no-plover` to turn
  this off). The page posts each layer signal to the app for this.
- Steno practice view (the app's main use): on the Steno layer the page keeps the
  last chord lit until the next one starts, shows the stroke large in steno order
  (Plover notation, coloured by key group), and keeps a paper tape of recent
  strokes in fixed columns. The word beside each stroke is a lookup the app does
  in Plover's default dictionaries (`user.json`, `commands.json`, `main.json`),
  trying the longest run of recent strokes first. It is a dictionary lookup, not
  Plover's actual output, so it can differ for affixes and unusual entries.
- Karabiner-Elements is installed on Kurt's Mac. It grabs keyboards
  exclusively, which hides them from the app, so the Corne is in its ignored
  devices (Kurt's Karabiner rules don't apply on the Corne).
- Keys and layer following were confirmed on the keyboard on 2026-10-12. The
  Plover switching was only confirmed as far as the command reaching Plover.

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
