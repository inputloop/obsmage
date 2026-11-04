#!/usr/bin/env python3
"""obs_load_check.py: on Windows, load obsmage-core into OBS Studio's own libobs, from where the installer put it.

    python obs_load_check.py OBS_DIR [--expect-version V]    exit 0 loaded; 1 not loaded; 2 usage
    python obs_load_check.py --prove-red OBS_DIR --expect-version V
                                                             the good run must pass, three planted faults must fail

OBS_DIR is an OBS Studio folder (the one that holds bin\\64bit\\obs64.exe) after the obsmage installer ran. This
loads OBS's own obs.dll and obs-frontend-api.dll from bin\\64bit, starts libobs without video, opens
obs-plugins\\64bit\\obsmage-core.dll with data\\obs-plugins\\obsmage-core as its data folder (the paths OBS Studio
gives a plugin there), initialises it, which runs the plugin's obs_module_load, then shuts libobs down, which runs
its obs_module_unload. Every libobs log line is printed.

Loaded means: obs_open_module returned MODULE_SUCCESS; obs_init_module returned true; the module describes itself
as "obsmage core"; its locale file answered from the data folder; and the plugin logged
"[obsmage-core] version V". There is no frontend here, so the plugin's Tools-menu calls only log a warning.
Windows, 64-bit Python 3.8 or later, standard library only (ctypes). The Linux counterpart is
packaging/healer/omg-load-check, which runs OBS Studio itself.
"""
import ctypes
import os
import subprocess
import sys

MODULE_CODES = {0: "MODULE_SUCCESS", -1: "MODULE_ERROR", -2: "MODULE_FAILED_TO_OPEN", -3: "MODULE_MISSING_EXPORTS",
                -4: "MODULE_INCOMPATIBLE_VER", -5: "MODULE_HARDCODED_SKIP"}
LEVELS = {100: "error", 200: "warning", 300: "info", 400: "debug"}
C = ctypes


def load(obs_dir, version, module=None):
    bin64 = os.path.join(obs_dir, "bin", "64bit")
    plugin = module or os.path.join(obs_dir, "obs-plugins", "64bit", "obsmage-core.dll")
    data = os.path.join(obs_dir, "data", "obs-plugins", "obsmage-core")
    if C.sizeof(C.c_void_p) != 8:
        print("obs_load_check: needs a 64-bit Python, like OBS Studio")
        return 2
    os.add_dll_directory(bin64)
    os.environ["PATH"] = bin64 + os.pathsep + os.environ.get("PATH", "")
    obs = C.CDLL(os.path.join(bin64, "obs.dll"))
    C.CDLL(os.path.join(bin64, "obs-frontend-api.dll"))  # as obs64.exe beside it would; the plugin imports it

    # libobs hands its log lines over as (level, format, va_list); the C runtime OBS uses formats them
    fmt = C.CDLL("ucrtbase").__stdio_common_vsprintf
    fmt.argtypes = [C.c_ulonglong, C.c_char_p, C.c_size_t, C.c_char_p, C.c_void_p, C.c_void_p]
    lines = []
    Handler = C.CFUNCTYPE(None, C.c_int, C.c_char_p, C.c_void_p, C.c_void_p)

    def on_log(level, msg, args, param):
        buf = C.create_string_buffer(8192)
        fmt(2, buf, len(buf), msg, None, args)  # 2: standard snprintf behaviour
        line = buf.value.decode("utf-8", "replace")
        lines.append(line)
        print("  libobs %-7s %s" % (LEVELS.get(level, level), line), flush=True)

    handler = Handler(on_log)
    obs.base_set_log_handler.argtypes = [Handler, C.c_void_p]
    obs.base_set_log_handler(handler, None)
    obs.obs_get_version_string.restype = C.c_char_p
    obs.obs_startup.argtypes = [C.c_char_p, C.c_char_p, C.c_void_p]
    obs.obs_startup.restype = C.c_bool
    obs.obs_open_module.argtypes = [C.POINTER(C.c_void_p), C.c_char_p, C.c_char_p]
    obs.obs_open_module.restype = C.c_int
    obs.obs_init_module.argtypes = [C.c_void_p]
    obs.obs_init_module.restype = C.c_bool
    obs.obs_get_module_description.argtypes = [C.c_void_p]
    obs.obs_get_module_description.restype = C.c_char_p
    obs.obs_module_get_locale_string.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(C.c_char_p)]
    obs.obs_module_get_locale_string.restype = C.c_bool

    print("obs_load_check: libobs %s from %s" % (obs.obs_get_version_string().decode(), bin64), flush=True)
    if not obs.obs_startup(b"en-US", None, None):
        print("obs_load_check: NOT LOADED: obs_startup failed")
        return 1
    found = []
    mod = C.c_void_p()
    rc = obs.obs_open_module(C.byref(mod), plugin.replace("\\", "/").encode("utf-8"), data.replace("\\", "/").encode("utf-8"))
    found.append(("opened (%s)" % MODULE_CODES.get(rc, rc), rc == 0))
    if rc == 0:
        found.append(("initialised (obs_module_load returned true)", bool(obs.obs_init_module(mod))))
        desc = (obs.obs_get_module_description(mod) or b"").decode("utf-8", "replace")
        found.append(("describes itself as obsmage core (%r)" % desc, desc.startswith("obsmage core")))
        text = C.c_char_p()
        got = obs.obs_module_get_locale_string(mod, b"ComposeScreenMaps", C.byref(text)) and text.value
        found.append(("its locale answered from %s (%r)" % (data, got), got == b"obsmage: compose screen maps"))
    want = "[obsmage-core] version %s" % version if version else "[obsmage-core] version "
    found.append(("logged %r" % want, any(l == want if version else l.startswith(want) for l in lines)))
    for what, ok in found:
        print("  %s  %s" % ("ok " if ok else "RED", what))
    good = all(ok for _, ok in found)
    print("obs_load_check: %s %s" % ("LOADED" if good else "NOT LOADED:", "" if good else plugin), flush=True)
    obs.obs_shutdown()
    print("obs_load_check: libobs shut down", flush=True)
    return 0 if good else 1


def prove_red(obs_dir, version):
    me = [sys.executable, os.path.abspath(__file__), obs_dir, "--expect-version", version]
    bin64 = os.path.join(obs_dir, "bin", "64bit")
    runs = [("the good run", [], 0),
            ("a version other than the one built", ["--expect-version", version + ".99"], 1),
            ("a DLL that is not an OBS module", ["--module", os.path.join(bin64, "obs-frontend-api.dll")], 1),
            ("a plugin that is not there", ["--module", os.path.join(obs_dir, "obs-plugins", "64bit", "no-such.dll")], 1)]
    bad = 0
    for what, extra, want in runs:
        r = subprocess.run(me + extra, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=300)
        verdict = [l for l in r.stdout.splitlines() if l.startswith("obs_load_check: ") and "LOADED" in l]
        right = r.returncode == want
        bad += 0 if right else 1
        print("%s  %s (exit %d, wanted %d; %s)" % ("ok " if right else "RED", what, r.returncode, want, verdict[-1] if verdict else "no verdict"))
    print("PROVE-RED OK" if bad == 0 else "PROVE-RED FAILED")
    return 0 if bad == 0 else 1


def main(argv):
    red = "--prove-red" in argv
    args = [a for a in argv if a != "--prove-red"]
    version = module = None
    rest = []
    i = 0
    while i < len(args):
        if args[i] in ("--expect-version", "--module") and i + 1 < len(args):
            if args[i] == "--expect-version":
                version = args[i + 1]
            else:
                module = args[i + 1]
            i += 2
            continue
        rest.append(args[i])
        i += 1
    if len(rest) != 1 or not os.path.isfile(os.path.join(rest[0], "bin", "64bit", "obs.dll")) or (red and not version):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    return prove_red(rest[0], version) if red else load(rest[0], version, module)


if __name__ == "__main__":
    code = main(sys.argv[1:])
    sys.stdout.flush()
    os._exit(code)

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
