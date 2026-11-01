"""Tests for tools/omg_compose.py.  Run:
    python3 -m unittest discover -s tests -p 'test_compose.py' -v
Set OMG_PROVE_RED=1 to plant a fault and watch the suite go red.
"""
import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import omg_compose as oc  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
REAL_DIR = "/mnt/user-data/uploads/corwi/AppData/Roaming/obs-studio/basic/scenes"
REAL = os.path.join(REAL_DIR, "Corwin__Avalon_2024July.json")
RED = os.environ.get("OMG_PROVE_RED") == "1"


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def scene(col, name):
    return next(s for s in col["sources"] if s["id"] == "scene" and s["name"] == name)


class XrandrTests(unittest.TestCase):
    def test_listmonitors(self):
        with open(os.path.join(FIX, "xrandr-listmonitors.txt")) as f:
            d = oc.parse_xrandr(f.read())
        self.assertEqual([x["name"] for x in d], ["DP-1", "HDMI-1", "DP-2"])
        self.assertEqual((d[0]["w"], d[0]["h"], d[0]["x"], d[0]["y"]), (2560, 1440, 1920, 0))
        self.assertTrue(d[0]["primary"])
        self.assertFalse(d[1]["primary"])
        self.assertIn("id", d[0]["unknown"])  # says why the id is weak

    def test_query_skips_disconnected(self):
        with open(os.path.join(FIX, "xrandr-query.txt")) as f:
            d = oc.parse_xrandr(f.read())
        self.assertEqual([x["name"] for x in d], ["DP-1", "HDMI-1", "DP-2"])
        self.assertTrue(d[0]["primary"])
        self.assertEqual((d[2]["w"], d[2]["h"], d[2]["x"]), (1080, 1920, 4480))


class AuditTests(unittest.TestCase):
    def test_classification(self):
        a = oc.audit(load("three-heads.json"))
        by = {r["name"]: r["bind"] for r in a["sources"]}
        self.assertEqual(by, {"Left Head": "index", "Center Head": "index", "Right Head": "id"})
        want = 2 if not RED else 3   # planted fault when OMG_PROVE_RED=1
        self.assertEqual(a["summary"]["by_index"], want)
        self.assertEqual(a["summary"]["by_id"], 1)

    def test_resolution_and_uncaptured(self):
        ds = oc.normalize_displays(load("displays-four.json"))
        a = oc.audit(load("three-heads.json"), ds)
        by = {r["name"]: r["resolves_to"]["name"] for r in a["sources"]}
        self.assertEqual(by, {"Left Head": "Left", "Center Head": "Center", "Right Head": "Right"})
        self.assertEqual([d["name"] for d in a["uncaptured_displays"]], ["New"])
        self.assertIn("Displays no source captures", oc.audit_text(a))

    def test_unbound_is_index_zero(self):
        col = load("three-heads.json")
        col["sources"][0]["settings"] = {}
        ds = oc.normalize_displays(load("displays-four.json"))
        a = oc.audit(col, ds)
        self.assertEqual(a["summary"]["unbound"], 1)
        self.assertEqual(a["sources"][0]["resolves_to"]["name"], "Left")


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.col = load("three-heads.json")
        self.ds = oc.normalize_displays(load("displays-four.json"))

    def test_adds_fourth_binds_by_id_keeps_hand_positions(self):
        new, rep = oc.compose(self.col, self.ds)
        sc = scene(new, "Screenmap")
        self.assertEqual(len(sc["settings"]["items"]), 4)
        old = {i["name"]: i for i in scene(self.col, "Screenmap")["settings"]["items"]}
        for i in sc["settings"]["items"][:3]:
            self.assertEqual(i["pos"], old[i["name"]]["pos"])
            self.assertEqual(i["scale"], old[i["name"]]["scale"])
        newsrc = next(s for s in new["sources"] if s["name"].startswith("omg display"))
        self.assertEqual(newsrc["settings"]["monitor_id"], self.ds[3]["id"])
        self.assertIn("uuid", newsrc)
        self.assertNotIn(newsrc["uuid"], [s["uuid"] for s in self.col["sources"]])
        item = sc["settings"]["items"][3]
        self.assertEqual(item["id"], 4)
        self.assertEqual(item["source_uuid"], newsrc["uuid"])
        self.assertEqual(sc["settings"]["id_counter"], 4)
        # existing index-bound sources gain an id, keep the index
        left = next(s for s in new["sources"] if s["name"] == "Left Head")
        self.assertEqual(left["settings"], {"monitor": 0, "monitor_id": self.ds[0]["id"]})
        self.assertTrue(any("stable id" in l for l in rep))
        # input untouched
        self.assertEqual(self.col, load("three-heads.json"))

    def test_new_item_fits_inside_canvas(self):
        new, _ = oc.compose(self.col, self.ds, margin=24)
        it = scene(new, "Screenmap")["settings"]["items"][3]
        right = it["pos"]["x"] + 1920 * it["scale"]["x"]
        self.assertLessEqual(right, 1920 - 24 + 1e-6)
        self.assertGreaterEqual(it["pos"]["x"], 24)

    def test_hides_removed_display_never_deletes(self):
        ds = [d for d in self.ds if d["name"] != "Right"]
        for n, d in enumerate(ds):
            d["index"] = n
        new, rep = oc.compose(self.col, ds)
        items = {i["name"]: i for i in scene(new, "Screenmap")["settings"]["items"]}
        self.assertIn("Right Head", items)
        self.assertFalse(items["Right Head"]["visible"])
        self.assertTrue(items["Left Head"]["visible"])
        self.assertTrue(any("not deleted" in l.lower() for l in rep))
        self.assertTrue(any(s["name"] == "Right Head" for s in new["sources"]))
        # and it comes back when the display returns
        back, rep2 = oc.compose(new, self.ds)
        it = next(i for i in scene(back, "Screenmap")["settings"]["items"] if i["name"] == "Right Head")
        self.assertTrue(it["visible"])
        self.assertTrue(any("Un-hid" in l for l in rep2))

    def test_relayout_moves_items(self):
        new, _ = oc.compose(self.col, self.ds, relayout=True)
        a = next(i for i in scene(new, "Screenmap")["settings"]["items"] if i["name"] == "Left Head")
        self.assertNotEqual(a["pos"], {"x": 100, "y": 300})

    def test_creates_scene_when_none(self):
        col = copy.deepcopy(self.col)
        scene(col, "Screenmap")["name"] = "Other"
        col["scene_order"] = [{"name": "Other"}]
        new, _ = oc.compose(col, self.ds)
        s = scene(new, "Screenmap (obsmage)")
        self.assertEqual(len(s["settings"]["items"]), 4)
        self.assertIn({"name": "Screenmap (obsmage)"}, new["scene_order"])

    def test_idempotent(self):
        once, _ = oc.compose(self.col, self.ds)
        twice, rep = oc.compose(once, self.ds)
        self.assertEqual(once, twice)

    def test_round_trip_json_and_cli_write_backup(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "c.json")
            with open(os.path.join(FIX, "three-heads.json"), "rb") as f:
                orig = f.read()
            with open(p, "wb") as f:
                f.write(orig)
            rc = oc.main(["compose", p, "--displays", os.path.join(FIX, "displays-four.json"), "--write"])
            self.assertEqual(rc, 0)
            baks = [n for n in os.listdir(t) if n.endswith(".bak")]
            self.assertEqual(len(baks), 1)
            with open(os.path.join(t, baks[0]), "rb") as f:
                self.assertEqual(f.read(), orig)
            with open(p, encoding="utf-8") as f:
                data = json.load(f)       # valid JSON
            self.assertEqual(len(scene(data, "Screenmap")["settings"]["items"]), 4)
            out = os.path.join(t, "o.json")
            oc.main(["compose", p, "--displays", os.path.join(FIX, "displays-four.json"), "--out", out])
            with open(out, encoding="utf-8") as f:
                self.assertEqual(json.load(f), data)

    def test_geometry_required(self):
        ds = copy.deepcopy(self.ds)
        ds[0]["x"] = None
        with self.assertRaises(ValueError):
            oc.compose(self.col, ds)


@unittest.skipUnless(os.path.exists(REAL), "real Corwin collection not staged here")
class RealFileTests(unittest.TestCase):
    def setUp(self):
        with open(REAL, encoding="utf-8") as f:
            self.col = json.load(f)

    def test_audit_numbers(self):
        # Observed by hand first: 12 monitor_capture = 8 by index + 1 unbound ({}) + 3 by id.
        s = oc.audit(self.col)["summary"]
        self.assertEqual(s["display_capture_sources"], 12)
        self.assertEqual((s["by_index"], s["by_id"], s["unbound"]), (8, 3, 1))

    def test_infer_layout(self):
        ds, notes = oc.infer_layout(self.col, "Screenmap")
        self.assertEqual(len(ds), 8)
        self.assertTrue(all(d["w"] > 0 and d["h"] > 0 for d in ds))
        x = {d["name"]: d["x"] for d in ds}
        self.assertLess(x["DC_Left"], x["DC_Main"])      # hand layout: Left sits left of Main
        self.assertTrue(any("assumed" in n for n in notes))
        # feeds straight into the composer
        new, rep = oc.compose(self.col, oc.normalize_displays(ds), ["Screenmap"])
        self.assertTrue(rep)


if __name__ == "__main__":
    unittest.main()

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later
# Mentat (for Corwin; claude-sonnet via subagent)
