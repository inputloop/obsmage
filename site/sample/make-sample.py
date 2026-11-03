#!/usr/bin/env python3
"""make-sample.py: writes the site demo's OBS configuration, invented from end to end.

    python3 site/sample/make-sample.py          (writes site/sample/config/ and displays.json)

Nothing here comes from anyone's real setup: the profile, the screens, the device paths, the
"secrets" (FAKE..., so a reader sees at once they are not real) and the host (example.invalid,
a name reserved never to resolve). The shapes are what OBS Studio 32 writes on Windows: a
basic.ini with a byte-order mark and CRLF endings, JSON with four-space indent. The screen map
is placed the way omg_compose.py places one (fit the displays' bounding box into the canvas),
and then one item is nudged by hand, as people do.
Standard library only; the output is the same bytes on every run.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "config")

DISPLAYS = [
    {"id": "\\\\?\\DISPLAY#SMP1920#4&010203&0&UID4351#{e6f07b5f-ee97-4a90-b076-33f57bf4eaa7}",
     "index": 0, "name": "Left", "x": 0, "y": 180, "w": 1920, "h": 1080, "primary": False},
    {"id": "\\\\?\\DISPLAY#SMP2560#4&0a0b0c&0&UID4352#{e6f07b5f-ee97-4a90-b076-33f57bf4eaa7}",
     "index": 1, "name": "Centre", "x": 1920, "y": 0, "w": 2560, "h": 1440, "primary": True},
    {"id": "\\\\?\\DISPLAY#SMP1080#4&0d0e0f&0&UID4353#{e6f07b5f-ee97-4a90-b076-33f57bf4eaa7}",
     "index": 2, "name": "Right", "x": 4480, "y": -120, "w": 1080, "h": 1920, "primary": False},
]
CANVAS = (1920, 1080)
MARGIN = 24


def uid(n):
    return "00000000-0000-4000-8000-%012d" % n


def fit():
    x0 = min(d["x"] for d in DISPLAYS); y0 = min(d["y"] for d in DISPLAYS)
    x1 = max(d["x"] + d["w"] for d in DISPLAYS); y1 = max(d["y"] + d["h"] for d in DISPLAYS)
    s = min((CANVAS[0] - 2 * MARGIN) / (x1 - x0), (CANVAS[1] - 2 * MARGIN) / (y1 - y0))
    ox = (CANVAS[0] - (x1 - x0) * s) / 2; oy = (CANVAS[1] - (y1 - y0) * s) / 2
    return [(round(ox + (d["x"] - x0) * s, 1), round(oy + (d["y"] - y0) * s, 1), round(s, 4)) for d in DISPLAYS]


def item(name, n, x, y, sx, sy, visible=True):
    return {"name": name, "source_uuid": uid(n), "visible": visible, "locked": False, "rot": 0.0,
            "scale_ref": {"x": 1920.0, "y": 1080.0}, "align": 5, "bounds_type": 0, "bounds_align": 0,
            "bounds_crop": False, "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
            "id": n, "group_item_backup": False, "pos": {"x": x, "y": y}, "pos_rel": {"x": 0.0, "y": 0.0},
            "scale": {"x": sx, "y": sy}, "scale_rel": {"x": sx, "y": sy}, "bounds": {"x": 0.0, "y": 0.0},
            "blend_method": "default", "blend_type": "normal", "show_transition": {"duration": 0},
            "hide_transition": {"duration": 0}, "private_settings": {}}


def source(name, n, sid, settings, versioned_id=None):
    return {"prev_ver": 536936451, "name": name, "uuid": uid(n), "id": sid, "versioned_id": versioned_id or sid,
            "settings": settings, "mixers": 0, "sync": 0, "flags": 0, "volume": 1.0, "balance": 0.5,
            "enabled": True, "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
            "push-to-talk": False, "push-to-talk-delay": 0, "hotkeys": {}, "deinterlace_mode": 0,
            "deinterlace_field_order": 0, "monitoring_type": 0, "private_settings": {}}


def scene_collection():
    (lx, ly, ls), (cx, cy, cs), (rx, ry, rs) = fit()
    lx = round(lx + 6.0, 1)   # nudged by hand: the composer keeps hand placement
    srcs = [
        source("Left screen", 1, "monitor_capture", {"monitor": 0, "capture_cursor": True}),
        source("Centre screen", 2, "monitor_capture", {"monitor": 1, "monitor_id": DISPLAYS[1]["id"], "capture_cursor": True}),
        source("Right screen", 3, "monitor_capture", {"capture_cursor": True}),
        source("Camera", 4, "dshow_input", {"video_device_id": "Sample Camera:\\\\?\\usb#vid_0000&pid_0000&mi_00#sample#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\\global",
                                            "res_type": 1, "resolution": "1280x720"}),
        source("Lower third", 5, "text_gdiplus", {"text": "Sample Studio \u00b7 live from the desk", "font": {"face": "Sans Serif", "size": 48, "style": "Regular", "flags": 0},
                                                  "color": 4294967295, "outline": True}, "text_gdiplus_v3"),
        source("Frame", 6, "image_source", {"file": "C:\\Users\\you\\Pictures\\sample-frame.png"}),
        source("Screenmap", 7, "scene", {"id_counter": 3, "custom_size": False, "items": [
            item("Left screen", 1, lx, ly, ls, ls), item("Centre screen", 2, cx, cy, cs, cs),
            item("Right screen", 3, rx, ry, rs, rs)]}),
        source("Live", 8, "scene", {"id_counter": 4, "custom_size": False, "items": [
            item("Centre screen", 2, 0.0, 0.0, 0.75, 0.75), item("Camera", 4, 1440.0, 760.0, 0.375, 0.375),
            item("Frame", 6, 0.0, 0.0, 1.0, 1.0), item("Lower third", 5, 64.0, 960.0, 1.0, 1.0)]}),
    ]
    return {"current_scene": "Live", "current_program_scene": "Live",
            "scene_order": [{"name": "Live"}, {"name": "Screenmap"}],
            "name": "Sample Desk", "sources": srcs, "groups": [], "quick_transitions": [],
            "transitions": [], "saved_projectors": [], "current_transition": "Fade",
            "transition_duration": 300, "preview_locked": False, "scaling_enabled": False,
            "scaling_level": 0, "scaling_off_x": 0.0, "scaling_off_y": 0.0, "modules": {}, "version": 2}


def crlf_bom(lines):
    return b"\xef\xbb\xbf" + ("\r\n".join(lines) + "\r\n").encode("utf-8")


def main():
    files = {
        "global.ini": ("\n".join([
            "[General]", "Pre19Defaults=false", "Pre21Defaults=false", "FirstRun=true", "LastVersion=537001984", "",
            "[Basic]", "Profile=Sample Studio", "ProfileDir=Sample_Studio", "SceneCollection=Sample Desk",
            "SceneCollectionFile=Sample_Desk", "",
            "; obs-websocket: a made-up password, withheld like any other credential",
            "[OBSWebSocket]", "FirstLoad=false", "ServerEnabled=true", "ServerPort=4455", "AuthRequired=true",
            "ServerPassword=FAKEwebsocketPw42", ""]) + "\n").encode("utf-8"),
        "basic/profiles/Sample_Studio/basic.ini": crlf_bom([
            "[General]", "Name=Sample Studio", "",
            "[Video]", "BaseCX=1920", "BaseCY=1080", "OutputCX=1280", "OutputCY=720", "FPSType=0", "FPSCommon=30", "",
            "[Output]", "Mode=Simple", "",
            "[SimpleOutput]", "FilePath=C:\\Users\\you\\Videos", "RecFormat2=mkv", "VBitrate=2500", "ABitrate=160", "",
            "[Audio]", "SampleRate=48000", "ChannelSetup=Stereo", "",
            "[Twitch]", "Name=sample-channel", "Token=FAKEtwitchToken0000000", "RefreshToken=FAKErefresh000000000000000"]),
        "basic/profiles/Sample_Studio/service.json": (json.dumps(
            {"type": "rtmp_custom", "settings": {"server": "rtmp://live.example.invalid/app", "use_auth": False,
                                                 "bwtest": False, "key": "FAKE_stream_key_000000"}}, indent=4) + "\n").encode("utf-8"),
        "basic/scenes/Sample_Desk.json": (json.dumps(scene_collection(), indent=4, ensure_ascii=False) + "\n").encode("utf-8"),
    }
    for rel, data in files.items():
        p = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    with open(os.path.join(HERE, "displays.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"displays": DISPLAYS, "canvas": list(CANVAS), "note": "invented displays, as omg_compose.py displays writes them"}, indent=2) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
