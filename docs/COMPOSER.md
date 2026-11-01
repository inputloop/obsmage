# omg_compose: the multi-monitor scene composer

`tools/omg_compose.py` keeps the "screenmap" scenes of an OBS scene collection in step with the
displays you actually have. Python 3 standard library only.

## Why stable ids

OBS can bind a display capture two ways:

- by **index** (`settings.monitor`, a number in the OS enumeration order). Add, remove or reorder a
  display and the same number points at a different screen.
- by **stable id** (`settings.monitor_id`, on Windows a device path such as
  `\\?\DISPLAY#ACI27C4#5&...#{e6f07b5f-...}`). It follows the hardware.

A hand-made collection drifts toward index binding. In the collection this was written for,
12 `monitor_capture` sources break down as 8 by index, 3 by id, 1 with no binding at all (OBS
treats that as index 0). The composer adds `monitor_id` to index-bound sources and **keeps** the
index so older OBS builds still work.

## The never-delete rule

The composer never deletes a source or a scene item. A display that has gone away gets its item
set `visible=false` and marked (`private_settings.omg_hidden = "display-missing"`). When the display
returns, that item is shown again. Items you hid yourself are left alone. The change report names
every hide.

## Commands

```
omg_compose.py displays [--from FILE | --from-xrandr FILE]
omg_compose.py audit COLLECTION [--displays FILE] [--json]
omg_compose.py compose COLLECTION --displays FILE [--scene NAME ...] [--canvas WxH]
                       [--margin N] [--relayout] [--source-type TYPE] [--out FILE | --write]
omg_compose.py infer-layout COLLECTION [--scene Screenmap]
```

`displays` with no option reads the live machine: Windows (ctypes `EnumDisplayMonitors`,
`GetMonitorInfoW`, `EnumDisplayDevicesW`), Linux (`xrandr`), macOS (`system_profiler`, best effort).
Unknown fields are `null` and the display carries an `unknown` object saying why (xrandr has no
stable id; system_profiler has no position and no CGDisplay UUID).

`compose` with neither `--out` nor `--write` is a dry run that prints the report. `--write` copies
`<file>.YYYYMMDD-HHMMSS.bak` first.

## Examples (generic fixture)

`tests/fixtures/three-heads.json` has three captures (two by index, one by id) and a `Screenmap`
scene. `tests/fixtures/displays-four.json` has those three displays plus a new one.

```
$ omg_compose.py audit tests/fixtures/three-heads.json --displays tests/fixtures/displays-four.json
3 display-capture source(s): 2 bound by index ..., 1 bound by stable id, 0 unbound ...
- 'Left Head' [monitor_capture] is bound by index 0; resolves to display #0 Left
...
Displays no source captures:
- display #3 New (1920x1080 at 5760,0)

$ omg_compose.py compose tests/fixtures/three-heads.json --displays tests/fixtures/displays-four.json --out /tmp/new.json
Bound 'Left Head' by stable id (index 0 kept for older OBS) -> display #0 Left ...
Created source 'omg display GEN103-103' bound to display #3 New ...
[Screenmap] Kept hand-placed item(s) for display #0 Left ...
[Screenmap] Added item id 4 for display #3 New ... at (1428.0, 408.4), scale 0.2437.
```

To seed a new collection from your own hand layout: `infer-layout` writes a displays JSON from an
existing screenmap, which you can edit and feed to `compose --displays`.

## How placement works

New items: the bounding box of all display rectangles is fitted into the canvas minus the margin
with one uniform scale, centred, keeping relative physical layout and aspect. Existing items for
present displays keep their hand-placed position and scale unless `--relayout`. New sources and items
get fresh uuid4 values and item ids (max existing id or `id_counter`, plus 1); fields such as
`pos_rel` and `source_uuid` are written only if the file already uses them.

## Limits

- A new item uses the global fit, not your hand layout, so it may overlap hand-placed neighbours.
- `infer-layout` assumes 1920x1080 native size (the collection does not store it) and does not
  expand group items.
- Windows device-path enumeration and the macOS path are untested here; Linux xrandr parsing is tested.
- Two sources bound to the same display (for example crops) are each reported; only the first
  (id-bound preferred) is upgraded to a stable id.
- Wayland pipewire captures cannot be bound or resolved; they are listed as unbound.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-sonnet via subagent)
