#!/usr/bin/env python3
"""omg_compose: multi-monitor scene detector and auto-composer for obsmage.

Subcommands: displays, audit, compose, infer-layout.  Python 3 standard library only.
Run `omg_compose.py --help` or see docs/COMPOSER.md.

Two piles, kept apart in this file:
  OBSERVED  - read from the OS or from the collection file (displays, audit).
  JUDGED    - decided by this tool (compose, infer-layout); every judgement is
              named in the change report so a person can overrule it.
"""
import argparse
import copy
import datetime
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import uuid

# source id -> (settings key for index binding, settings key for stable-id binding)
BIND_KEYS = {
    "monitor_capture": ("monitor", "monitor_id"),      # Windows
    "display_capture": ("display", "display_uuid"),    # macOS (older OBS id)
    "screen_capture": ("display", "display_uuid"),     # macOS (newer OBS id)
    "xshm_input": ("screen", None),                    # Linux X11
    "pipewire-desktop-capture-source": (None, None),   # Linux Wayland: portal picks
    "pipewire-screen-capture-source": (None, None),
}
NATIVE_GUESS = (1920, 1080)
ASSUMED_BY_US = "omg_hidden"   # item.private_settings marker set when WE hide an item


# --------------------------------------------------------------------------- displays

def _disp(index, name, x, y, w, h, primary, did, unknown=None):
    d = {"id": did, "index": index, "name": name, "x": x, "y": y, "w": w, "h": h,
         "primary": primary}
    if unknown:
        d["unknown"] = unknown
    return d


def normalize_displays(raw):
    """Accept a list of display dicts (or {"displays": [...]}); fill missing keys with None."""
    if isinstance(raw, dict) and "displays" in raw:
        raw = raw["displays"]
    if not isinstance(raw, list):
        raise ValueError("displays JSON must be a list of display objects")
    out = []
    for n, d in enumerate(raw):
        e = {k: d.get(k) for k in ("id", "index", "name", "x", "y", "w", "h", "primary")}
        if e["index"] is None:
            e["index"] = n
        if e["primary"] is None:
            e["primary"] = False
        if "unknown" in d:
            e["unknown"] = d["unknown"]
        out.append(e)
    return out


def load_displays_file(path):
    with open(path, encoding="utf-8") as f:
        return normalize_displays(json.load(f))


_RE_LISTMON = re.compile(
    r"^\s*(\d+):\s+([+*]*)(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)")
_RE_QUERY = re.compile(
    r"^(\S+)\s+connected(\s+primary)?\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")


def parse_xrandr(text):
    """Parse `xrandr --listmonitors` or `xrandr --query` text into display dicts."""
    why = {"id": "xrandr gives an output name, not a stable hardware id; "
                 "OBS xshm_input binds by screen index only"}
    out = []
    if "Monitors:" in text:
        for line in text.splitlines():
            m = _RE_LISTMON.match(line)
            if m:
                i, flags, name, w, h, x, y = m.groups()
                out.append(_disp(int(i), name, int(x), int(y), int(w), int(h),
                                 "*" in flags, name, why))
    else:
        for line in text.splitlines():
            m = _RE_QUERY.match(line)
            if m:
                name, prim, w, h, x, y = m.groups()
                out.append(_disp(len(out), name, int(x), int(y), int(w), int(h),
                                 bool(prim), name, why))
    return out


def enumerate_linux():
    for cmd in (["xrandr", "--listmonitors"], ["xrandr", "--query"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0:
            d = parse_xrandr(r.stdout)
            if d:
                return d
    raise RuntimeError("xrandr is missing or reported no active monitors "
                       "(Wayland-only session? give --from or --from-xrandr)")


def enumerate_macos():
    r = subprocess.run(["system_profiler", "SPDisplaysDataType", "-json"],
                       capture_output=True, text=True, timeout=30)
    data = json.loads(r.stdout)
    out = []
    why = {"x": "system_profiler does not report display position",
           "y": "system_profiler does not report display position",
           "id": "OBS binds by CGDisplay UUID, which system_profiler does not report"}
    for gpu in data.get("SPDisplaysDataType", []):
        for nd in gpu.get("spdisplays_ndrvs", []):
            px = nd.get("_spdisplays_pixels") or nd.get("_spdisplays_resolution") or ""
            m = re.match(r"\s*(\d+)\s*x\s*(\d+)", px)
            w, h = (int(m.group(1)), int(m.group(2))) if m else (None, None)
            out.append(_disp(len(out), nd.get("_name"), None, None, w, h,
                             nd.get("spdisplays_main") == "spdisplays_yes", None, dict(why)))
    return out


def enumerate_windows():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    # Without this, Windows hands a scaled-display process virtualised (smaller) sizes.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    class DISPLAY_DEVICEW(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
                    ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
                    ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]

    found = []
    PROTO = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                               ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, hdc, rect, lparam):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            found.append((mi.szDevice, mi.rcMonitor.left, mi.rcMonitor.top,
                          mi.rcMonitor.right - mi.rcMonitor.left,
                          mi.rcMonitor.bottom - mi.rcMonitor.top, bool(mi.dwFlags & 1)))
        return True

    # explicit types: a 32-bit Python 3.8 and a 64-bit one both pass handles correctly
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), PROTO,
                                           wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                                           wintypes.DWORD]
    user32.EnumDisplayDevicesW.restype = wintypes.BOOL
    user32.EnumDisplayMonitors(None, None, PROTO(cb), 0)
    out = []
    for dev, x, y, w, h, prim in found:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        # EDD_GET_DEVICE_INTERFACE_NAME (1) makes DeviceID the \\?\DISPLAY#...# path
        ok = user32.EnumDisplayDevicesW(dev, 0, ctypes.byref(dd), 1)
        did = dd.DeviceID if ok and dd.DeviceID else None
        name = dd.DeviceString if ok and dd.DeviceString else dev
        out.append(_disp(len(out), name, x, y, w, h, prim, did,
                         None if did else {"id": "EnumDisplayDevicesW returned no device path"}))
    return out


def detect_displays():
    if sys.platform.startswith("win"):
        return enumerate_windows()
    if sys.platform == "darwin":
        return enumerate_macos()
    return enumerate_linux()


# --------------------------------------------------------------------------- collection helpers

def load_collection(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sources_of(col):
    return col.get("sources", [])


def classify_source(src):
    """Return a bind record for a display-capture source, or None if it is not one."""
    sid = src.get("id")
    if sid not in BIND_KEYS:
        return None
    st = src.get("settings") or {}
    if sid == "screen_capture" and st.get("type", 0) != 0:
        return None  # window / application capture on macOS
    ikey, dkey = BIND_KEYS[sid]
    idx = st.get(ikey) if ikey else None
    did = st.get(dkey) if dkey else None
    if did == "":
        did = None
    if did is not None:
        kind = "id"
    elif idx is not None:
        kind = "index"
    else:
        kind = "unbound"
    return {"name": src.get("name"), "uuid": src.get("uuid"), "type": sid, "bind": kind,
            "index": idx, "id": did, "index_key": ikey, "id_key": dkey}


def resolve(rec, displays):
    """Which display does this bind record capture?  Returns (display|None, notes)."""
    notes = []
    by_id = None
    by_idx = None
    if rec["id"] is not None:
        by_id = next((d for d in displays if d["id"] and d["id"].casefold() == rec["id"].casefold()), None)
    if rec["index"] is not None:
        by_idx = next((d for d in displays if d["index"] == rec["index"]), None)
    if rec["bind"] == "id":
        if by_id is None:
            notes.append("id matches no current display" +
                         ("; OBS would fall back to its index" if rec["index"] is not None else ""))
            return None, notes
        if rec["index"] is not None and (by_idx is None or by_idx is not by_id):
            notes.append("index %s now points elsewhere; the id wins" % rec["index"])
        return by_id, notes
    if rec["bind"] == "index":
        if by_idx is None:
            notes.append("index %s matches no current display" % rec["index"])
        return by_idx, notes
    if rec["type"].startswith("pipewire"):
        notes.append("Wayland portal chooses the display at runtime; cannot be resolved here")
        return None, notes
    d = next((d for d in displays if d["index"] == 0), None)
    notes.append("no binding set; OBS defaults to monitor index 0")
    return d, notes


def short_name(d, taken):
    m = re.match(r"\\\\\?\\DISPLAY#([^#]+)#[^#]*?UID(\d+)#", d.get("id") or "", re.I)
    if m:
        base = "%s-%s" % (m.group(1), m.group(2))
    elif d.get("id"):
        base = re.sub(r"[^A-Za-z0-9_.-]+", "-", d["id"]).strip("-")[:40]
    elif d.get("name"):
        base = re.sub(r"[^A-Za-z0-9_.-]+", "-", d["name"]).strip("-")[:40]
    else:
        base = "display%s" % d["index"]
    name, n = "omg display " + base, 2
    while name in taken:
        name = "omg display %s-%d" % (base, n)
        n += 1
    return name


def describe(d):
    if d is None:
        return "no current display"
    return "display #%s %s (%sx%s at %s,%s)" % (d["index"], d["name"] or d["id"], d["w"], d["h"], d["x"], d["y"])


# --------------------------------------------------------------------------- audit

def audit(col, displays=None):
    recs, skipped = [], 0
    for s in sources_of(col):
        r = classify_source(s)
        if r is None:
            if s.get("id") == "screen_capture":
                skipped += 1
            continue
        if displays is not None:
            disp, notes = resolve(r, displays)
            r["resolves_to"] = None if disp is None else {
                "index": disp["index"], "id": disp["id"], "name": disp["name"]}
            r["notes"] = notes
        recs.append(r)
    summary = {"display_capture_sources": len(recs),
               "by_index": sum(r["bind"] == "index" for r in recs),
               "by_id": sum(r["bind"] == "id" for r in recs),
               "unbound": sum(r["bind"] == "unbound" for r in recs),
               "skipped_window_or_app_captures": skipped}
    out = {"sources": recs, "summary": summary}
    if displays is not None:
        hit = {r["resolves_to"]["index"] for r in recs if r["resolves_to"]}
        out["uncaptured_displays"] = [d for d in displays if d["index"] not in hit]
    return out


def audit_text(a):
    s = a["summary"]
    L = ["%d display-capture source(s): %d bound by index (fragile: shifts when displays "
         "change), %d bound by stable id, %d unbound (OBS uses index 0)." %
         (s["display_capture_sources"], s["by_index"], s["by_id"], s["unbound"])]
    if s["skipped_window_or_app_captures"]:
        L.append("(%d macOS screen_capture source(s) capture a window or app and were skipped.)"
                 % s["skipped_window_or_app_captures"])
    for r in a["sources"]:
        if r["bind"] == "id":
            how = "bound by id %s%s" % (r["id"], " (index %s also set)" % r["index"] if r["index"] is not None else "")
        elif r["bind"] == "index":
            how = "bound by index %s" % r["index"]
        else:
            how = "not bound to anything"
        line = "- %r [%s] is %s" % (r["name"], r["type"], how)
        if "resolves_to" in r:
            rt = r["resolves_to"]
            line += "; resolves to " + ("display #%s %s" % (rt["index"], rt["name"] or rt["id"]) if rt else "no current display")
            if r["notes"]:
                line += " (" + "; ".join(r["notes"]) + ")"
        L.append(line)
    if "uncaptured_displays" in a:
        if a["uncaptured_displays"]:
            L.append("Displays no source captures:")
            L += ["- " + describe(d) for d in a["uncaptured_displays"]]
        else:
            L.append("Every current display is captured by at least one source.")
    return "\n".join(L)


# --------------------------------------------------------------------------- compose

def scenes_of(col):
    return [s for s in sources_of(col) if s.get("id") == "scene"]


def make_scene(col, name, have_uuid):
    tmpl = next(iter(scenes_of(col)), None)
    sc = copy.deepcopy(tmpl) if tmpl else {
        "prev_ver": 0, "id": "scene", "versioned_id": "scene", "mixers": 0, "sync": 0, "flags": 0,
        "volume": 1.0, "balance": 0.5, "enabled": True, "muted": False, "private_settings": {}}
    sc["name"] = name
    if have_uuid:
        sc["uuid"] = str(uuid.uuid4())
    else:
        sc.pop("uuid", None)
    sc["settings"] = {"custom_size": False, "id_counter": 0, "items": []}
    sc["hotkeys"] = {"OBSBasic.SelectScene": []}
    return sc


def make_capture(col, name, disp, stype, have_uuid):
    ikey, dkey = BIND_KEYS[stype]
    tmpl = next((s for s in sources_of(col) if s.get("id") == stype), None)
    src = copy.deepcopy(tmpl) if tmpl else {
        "prev_ver": 0, "id": stype, "versioned_id": stype, "mixers": 0, "sync": 0, "flags": 0,
        "volume": 1.0, "balance": 0.5, "enabled": True, "muted": False, "hotkeys": {},
        "private_settings": {}}
    src["name"] = name
    src["id"] = stype
    src["versioned_id"] = stype
    if have_uuid:
        src["uuid"] = str(uuid.uuid4())
    else:
        src.pop("uuid", None)
    st = {}
    if dkey and disp["id"]:
        st[dkey] = disp["id"]
    if ikey:
        st[ikey] = disp["index"]
    src["settings"] = st
    if "filters" in src:
        src["filters"] = []
    return src


def make_item(tmpl_item, src, x, y, s, canvas, have_uuid, have_rel, item_id):
    cw, ch = canvas
    it = copy.deepcopy(tmpl_item) if tmpl_item else {
        "name": "", "visible": True, "locked": False, "rot": 0.0, "align": 5,
        "bounds_type": 0, "bounds_align": 0, "bounds_crop": False,
        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
        "group_item_backup": False, "bounds": {"x": 0.0, "y": 0.0},
        "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
        "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
        "private_settings": {}}
    it["name"] = src["name"]
    if have_uuid:
        it["source_uuid"] = src["uuid"]
    it.update({"visible": True, "locked": False, "rot": 0.0, "id": item_id,
               "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
               "bounds_type": 0, "bounds": {"x": 0.0, "y": 0.0},
               "pos": {"x": x, "y": y}, "scale": {"x": s, "y": s},
               "private_settings": {}})
    if have_rel:
        it["scale_ref"] = {"x": float(cw), "y": float(ch)}
        it["pos_rel"] = {"x": (x - cw / 2.0) / (ch / 2.0), "y": (y - ch / 2.0) / (ch / 2.0)}
        it["scale_rel"] = {"x": s, "y": s}
        it["bounds_rel"] = {"x": 0.0, "y": 0.0}
    return it


def set_geometry(it, x, y, s, canvas):
    cw, ch = canvas
    it["pos"] = {"x": x, "y": y}
    it["scale"] = {"x": s, "y": s}
    if "pos_rel" in it:
        it["pos_rel"] = {"x": (x - cw / 2.0) / (ch / 2.0), "y": (y - ch / 2.0) / (ch / 2.0)}
        it["scale_rel"] = {"x": s, "y": s}


def fit(displays, canvas, margin):
    """Return (scale, fn(display)->(x,y)) fitting all display rects into canvas - margin."""
    x0 = min(d["x"] for d in displays)
    y0 = min(d["y"] for d in displays)
    bw = max(d["x"] + d["w"] for d in displays) - x0
    bh = max(d["y"] + d["h"] for d in displays) - y0
    cw, ch = canvas
    s = min((cw - 2 * margin) / bw, (ch - 2 * margin) / bh)
    ox = (cw - bw * s) / 2.0
    oy = (ch - bh * s) / 2.0
    return s, lambda d: (ox + (d["x"] - x0) * s, oy + (d["y"] - y0) * s)


def compose(col, displays, scene_names=None, canvas=None, margin=24, relayout=False,
            source_type="monitor_capture"):
    """Return (new_collection, report_lines).  The input is not modified."""
    col = copy.deepcopy(col)
    R = []
    bad = [d for d in displays if None in (d["x"], d["y"], d["w"], d["h"])]
    if bad:
        raise ValueError("displays without full geometry (x,y,w,h): %s; cannot compose. "
                         "Give a displays file that has them (see `displays` unknown fields)."
                         % ", ".join(str(d["name"] or d["index"]) for d in bad))
    if not displays:
        raise ValueError("no displays given")
    if source_type not in BIND_KEYS:
        raise ValueError("unknown source type %r" % source_type)
    ikey, dkey = BIND_KEYS[source_type]
    if dkey is None:
        R.append("NOTE: %s has no stable-id setting; new sources bind by index only." % source_type)
    for d in displays:
        if dkey and not d["id"]:
            R.append("WARNING: %s has no id; its source will bind by index only." % describe(d))
        elif source_type == "monitor_capture" and d["id"] and not d["id"].startswith("\\\\?\\"):
            R.append("WARNING: id %r is not a Windows device path; the id binding only works "
                     "in Windows OBS." % d["id"])
    srcs = sources_of(col)
    have_uuid = any("uuid" in s for s in srcs)
    have_rel = any("pos_rel" in i for sc in scenes_of(col) for i in sc["settings"].get("items", []))
    if canvas is None:
        res = col.get("resolution") or {}
        canvas = (res.get("x", 1920), res.get("y", 1080))
        if not res:
            R.append("NOTE: collection has no resolution; assumed canvas %dx%d." % canvas)

    # (a) one capture source per display, bound by stable id
    taken = {s.get("name") for s in srcs}
    chosen = {}   # display index -> source dict
    cands = {}
    for s in srcs:
        r = classify_source(s)
        if r is None or r["type"] != source_type:
            continue
        disp, _ = resolve(r, displays)
        if disp is not None:
            cands.setdefault(disp["index"], []).append((r["bind"] == "id", s, r))
    for d in displays:
        c = cands.get(d["index"], [])
        c.sort(key=lambda t: not t[0])   # id-bound first; sort is stable (file order)
        if c:
            _, s, r = c[0]
            chosen[d["index"]] = s
            if dkey and d["id"] and r["bind"] != "id":
                s["settings"][dkey] = d["id"]
                if r["bind"] == "index":
                    R.append("Bound %r by stable id (index %s kept for older OBS) -> %s." %
                             (s["name"], r["index"], describe(d)))
                else:
                    R.append("Bound %r (was unbound, i.e. index 0) by stable id -> %s." %
                             (s["name"], describe(d)))
            else:
                R.append("Reused %r for %s." % (s["name"], describe(d)))
        else:
            name = short_name(d, taken)
            taken.add(name)
            s = make_capture(col, name, d, source_type, have_uuid)
            srcs.append(s)
            chosen[d["index"]] = s
            R.append("Created source %r bound to %s." % (name, describe(d)))

    # (b)-(d) scenes
    all_scenes = scenes_of(col)
    if scene_names:
        targets = []
        for n in scene_names:
            sc = next((s for s in all_scenes if s["name"] == n), None)
            if sc is None:
                sc = make_scene(col, n, have_uuid)
                srcs.append(sc)
                col.setdefault("scene_order", []).append({"name": n})
                R.append("Created scene %r." % n)
            targets.append(sc)
    else:
        targets = [s for s in all_scenes if "screenmap" in s["name"].lower()]
        if not targets:
            sc = make_scene(col, "Screenmap (obsmage)", have_uuid)
            srcs.append(sc)
            col.setdefault("scene_order", []).append({"name": sc["name"]})
            R.append("No Screenmap scene found; created %r." % sc["name"])
            targets = [sc]
    by_uuid = {s["uuid"]: s for s in srcs if "uuid" in s}
    by_name = {s["name"]: s for s in srcs}
    scale, place = fit(displays, canvas, margin)

    for sc in targets:
        st = sc["settings"]
        items = st.setdefault("items", [])
        tmpl = items[0] if items else None
        seen = {}
        for it in items:
            src = by_uuid.get(it.get("source_uuid")) or by_name.get(it.get("name"))
            r = classify_source(src) if src else None
            if r is None:
                continue
            disp, _ = resolve(r, displays)
            if disp is None:
                if it.get("visible", True):
                    it["visible"] = False
                    it.setdefault("private_settings", {})[ASSUMED_BY_US] = "display-missing"
                    R.append("[%s] Hid item %r (id %s): its display is gone. Not deleted." %
                             (sc["name"], it["name"], it.get("id")))
                continue
            seen.setdefault(disp["index"], []).append(it)
            ps = it.get("private_settings") or {}
            if ps.get(ASSUMED_BY_US) == "display-missing":
                it["visible"] = True
                del ps[ASSUMED_BY_US]
                R.append("[%s] Un-hid item %r: its display is back." % (sc["name"], it["name"]))
            if relayout:
                x, y = place(disp)
                set_geometry(it, x, y, scale, canvas)
                R.append("[%s] Re-laid-out %r (--relayout)." % (sc["name"], it["name"]))
        for d in displays:
            if d["index"] in seen:
                if not relayout:
                    R.append("[%s] Kept hand-placed item(s) for %s." % (sc["name"], describe(d)))
                continue
            src = chosen[d["index"]]
            nid = max([i.get("id", 0) for i in items] + [st.get("id_counter", 0)]) + 1
            x, y = place(d)
            items.append(make_item(tmpl, src, x, y, scale, canvas, have_uuid, have_rel, nid))
            st["id_counter"] = nid
            hk = sc.get("hotkeys")
            if isinstance(hk, dict):
                hk.setdefault("libobs.show_scene_item.%d" % nid, [])
                hk.setdefault("libobs.hide_scene_item.%d" % nid, [])
            R.append("[%s] Added item id %d for %s at (%.1f, %.1f), scale %.4f." %
                     (sc["name"], nid, describe(d), x, y, scale))
    if not any(l.startswith(("Created", "Bound", "[")) for l in R):
        R.append("Nothing to change.")
    return col, R


# --------------------------------------------------------------------------- infer-layout

def infer_layout(col, scene_name):
    sc = next((s for s in scenes_of(col) if s["name"] == scene_name), None)
    if sc is None:
        raise ValueError("no scene named %r" % scene_name)
    by_uuid = {s["uuid"]: s for s in sources_of(col) if "uuid" in s}
    by_name = {s["name"]: s for s in sources_of(col)}
    rows, notes, seen = [], [], set()
    for it in sc["settings"].get("items", []):
        src = by_uuid.get(it.get("source_uuid")) or by_name.get(it.get("name"))
        r = classify_source(src) if src else None
        if r is None:
            notes.append("skipped item %r: not a display capture (groups are not expanded)" % it.get("name"))
            continue
        key = (r["id"], r["index"] if r["id"] is None else None, r["bind"] == "unbound")
        if key in seen:
            notes.append("skipped item %r: another item already shows the same display" % it.get("name"))
            continue
        seen.add(key)
        sx, sy = it["scale"]["x"], it["scale"]["y"]
        rows.append((it, src, r, sx, sy))
    if not rows:
        return [], notes
    s_ref = statistics.median(r[3] for r in rows)
    notes.append("native size unknown in the file; assumed %dx%d for every display" % NATIVE_GUESS)
    notes.append("thumbnail->physical factor = 1/%.4f (median item scale)" % s_ref)
    out = []
    for it, src, r, sx, sy in rows:
        left = it["pos"]["x"] - it.get("crop_left", 0) * sx   # un-crop to the whole display
        top = it["pos"]["y"] - it.get("crop_top", 0) * sy
        idx = r["index"] if r["index"] is not None else (0 if r["bind"] == "unbound" else None)
        unknown = {"w,h": "assumed %dx%d (native size is not stored in the collection)" % NATIVE_GUESS,
                   "primary": "not recorded in the collection"}
        if r["id"] is None:
            unknown["id"] = "source binds by index only"
        out.append(_disp(idx, src["name"], int(round(left / s_ref)), int(round(top / s_ref)),
                         NATIVE_GUESS[0], NATIVE_GUESS[1], False, r["id"], unknown))
    # shift so the layout starts at 0,0
    x0 = min(d["x"] for d in out)
    y0 = min(d["y"] for d in out)
    for d in out:
        d["x"] -= x0
        d["y"] -= y0
    return out, notes


# --------------------------------------------------------------------------- CLI

def parse_canvas(s):
    m = re.fullmatch(r"(\d+)x(\d+)", s)
    if not m:
        raise argparse.ArgumentTypeError("canvas must look like 1920x1080")
    return int(m.group(1)), int(m.group(2))


def dump_json(col, path):
    # newline="\n": on Windows text mode would write CRLF; OBS writes LF
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(col, f, indent=4, ensure_ascii=False)
        f.write("\n")


def build_parser():
    p = argparse.ArgumentParser(prog="omg_compose", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("displays", help="report current display geometry as JSON")
    a.add_argument("--from", dest="from_file", help="JSON file of displays")
    a.add_argument("--from-xrandr", help="text of `xrandr --listmonitors` or `--query`")
    a.add_argument("--out", help="write the JSON here (UTF-8, LF) instead of printing; use this "
                                 "on Windows, where PowerShell's > writes UTF-16")
    b = sub.add_parser("audit", help="how each display-capture source binds")
    b.add_argument("collection")
    b.add_argument("--displays", help="displays JSON; also resolves each source")
    b.add_argument("--json", action="store_true")
    c = sub.add_parser("compose", help="add/bind/hide so screenmap scenes match the displays")
    c.add_argument("collection")
    c.add_argument("--displays", required=True)
    c.add_argument("--scene", action="append", help="target scene (repeatable)")
    c.add_argument("--canvas", type=parse_canvas)
    c.add_argument("--margin", type=float, default=24)
    c.add_argument("--relayout", action="store_true")
    c.add_argument("--source-type", default="monitor_capture", choices=sorted(BIND_KEYS))
    g = c.add_mutually_exclusive_group()
    g.add_argument("--out")
    g.add_argument("--write", action="store_true", help="replace in place, with a dated .bak")
    d = sub.add_parser("infer-layout", help="derive display geometry from a hand-made scene")
    d.add_argument("collection")
    d.add_argument("--scene", default="Screenmap")
    return p


def _utf8_streams():
    """Windows consoles and redirects default to a legacy code page (cp1252); a source name with
    a character outside it would crash a print. Say UTF-8, and never crash on a stray character."""
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _utf8_streams()
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "displays":
            if args.from_file:
                ds = load_displays_file(args.from_file)
            elif args.from_xrandr:
                with open(args.from_xrandr, encoding="utf-8") as f:
                    ds = parse_xrandr(f.read())
            else:
                ds = detect_displays()
            if args.out:
                with open(args.out, "w", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps(ds, indent=2) + "\n")
                print("Wrote %s (%d display(s))" % (args.out, len(ds)))
            else:
                print(json.dumps(ds, indent=2))
        elif args.cmd == "audit":
            ds = load_displays_file(args.displays) if args.displays else None
            res = audit(load_collection(args.collection), ds)
            print(json.dumps(res, indent=2) if args.json else audit_text(res))
        elif args.cmd == "compose":
            col = load_collection(args.collection)
            new, rep = compose(col, load_displays_file(args.displays), args.scene, args.canvas,
                               args.margin, args.relayout, args.source_type)
            print("\n".join(rep))
            if args.write:
                bak = "%s.%s.bak" % (args.collection, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
                shutil.copy2(args.collection, bak)
                dump_json(new, args.collection)
                print("Wrote %s (backup: %s)" % (args.collection, bak))
            elif args.out:
                dump_json(new, args.out)
                print("Wrote %s" % args.out)
            else:
                print("(dry run: give --out FILE or --write to save)")
        elif args.cmd == "infer-layout":
            ds, notes = infer_layout(load_collection(args.collection), args.scene)
            for n in notes:
                print("note: " + n, file=sys.stderr)
            print(json.dumps(ds, indent=2))
    except (ValueError, RuntimeError, OSError) as e:
        print("omg_compose: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later
# Mentat (for Corwin; claude-sonnet via subagent)
