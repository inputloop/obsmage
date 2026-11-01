# AR desktop control — design

Status: **design, not built.** The calibration dock and the gesture engine below are specified
here so the plugin skeleton (`plugin/obsmage-core`) and the tests can grow toward them. Nothing in
this file claims to work yet.

## The promise to the person at the desk

You are always one move away from getting your desktop back. **Escape, Space, any mouse click,
opening a context menu or the Start menu** releases control at once, mid-gesture, and the window
being moved stays where it is. Release is checked on every frame, before any gesture logic runs.
A gesture never starts without first showing you what it thinks you meant (a jiggle, a spotlight)
and waiting for your confirmation.

## What it needs

- **Two or more cameras.** Ideally each one sees both the screens and you. Depth comes from
  the disagreement between views. One camera cannot tell a reach from a lean.
- **Calibration**, reachable from OBS's Tools menu whenever `obsmage-core` is loaded, even when no
  feature-module plugins are installed. This is for someone who adds a couple of our plugins to
  an upstream OBS they built themselves, not only for people on our full downstream build.
- **The physical-to-graphical map**: a local service (ours, or bring your own) that answers
  "this point in the room → this pixel on this display". Calibration produces it; every gesture
  consumes it.

## Calibration (core plugin, always available)

1. **Cameras.** List the video capture devices OBS already knows. The person ticks the ones that
   can see the desk.
2. **Screens.** Each display shows a large numbered marker (an ArUco-style tag) in turn. Each
   camera records where it sees each display's corners. This gives camera-to-screen geometry with
   no measuring tape.
3. **The person.** "Point at the marker on screen 2" for each screen, with an optional fingertip
   pass at the corners. This gives a camera-to-hand-to-screen ray.
4. **Check.** Show a spotlight wherever the system thinks you are pointing. The person confirms,
   or redoes the step that is off. Store the result as atoms (`calibration/<rig>/...`), so a
   calibration is versioned, diffable and reversible like the rest of the configuration.

The camera-to-display identity uses the composer's stable display ids (`docs/COMPOSER.md`), so a
re-plugged monitor does not silently invalidate a calibration. It shows as "screen 3 moved —
recalibrate screen 3?".

## Hand sensing

A separate local process (the **seer**) runs hand-landmark detection on each camera and
triangulates. It sends the plugin a small stream of hand states: per hand, a wrist pose, finger
extension (open, closed, pointing, spread) and velocity. It runs locally and sends nothing
anywhere. Telemetry is out of scope by decision (2026-11-01).

## The gestures (demo order: hardest to simplest)

Every gesture is a state machine: **IDLE → PROPOSE → CONFIRM → ACT → RELEASE**. PROPOSE always
shows the person its guess. CONFIRM is a deliberate move by the person. Any release signal from
any state goes straight to RELEASE.

### 1. Magic hand — grab and move a window
- PROPOSE: a closed fist aimed at a window → that window **jiggles in time with your wrist
  wiggle**, so you can see which window it picked.
- CONFIRM: you lift your wrist slightly, or start moving.
- ACT: the window follows the grab point.
- RELEASE: open the hand (a throw) → the window stops where it is. Optional, off by default:
  a throw carries momentum until it hits a display edge.

### 2. Flick to fill
- Same PROPOSE and CONFIRM as magic hand.
- ACT: fingers fly apart → the grabbed window goes fullscreen on the display it is on (the
  same as the OS maximize-to-fill action, not a new window mode).

### 3. Magic wand — a pointer you can see
- PROPOSE: one finger out, drawing a small circle.
- CONFIRM: a spotlight appears where you point. That appearing is the confirmation shown back to
  you.
- ACT: the spotlight follows your fingertip.
- RELEASE: drop the wrist, or put out more fingers.
- Moves the OS pointer only if the person turned that on. By default it is a presenter's
  spotlight drawn as an OBS overlay.

### 4. Wall grab — swipe between virtual desktops
- PROPOSE: a grab at an invisible wall to your left or right.
- CONFIRM: you pull.
- ACT: the OS switches virtual desktop in the direction you pulled yourself (pull from the
  right wall → move right).
- Uses the OS's own desktop-switch command. If the platform has none, the gesture is not
  offered, and the dock says why.

### 5. Multi-head scene composer — the simplest, and already built
Reads the display setup when OBS loads and updates the screen-map scenes. See
`docs/COMPOSER.md` and `tools/omg_compose.py`. This is the first feature module because it needs
no camera at all.

## Freedoms and consent

- Every feature module is a separate plugin. You can install the composer without ever loading
  the camera code.
- Cameras are opened only while AR control is switched on, and an indicator shows in OBS's
  status bar while they are open.
- Gesture definitions are atoms, readable and changeable like any other setting. The
  thresholds, the release signals and the momentum option are all yours to change.

## Falsifiers (each becomes a test when the code exists)

- F1: a release signal arriving mid-ACT leaves the window exactly where it was on the previous
  frame, every time (replay test over recorded hand streams).
- F2: no gesture reaches ACT without passing through PROPOSE, and PROPOSE always draws something
  (state-machine property test).
- F3: with zero or one camera, AR control refuses to switch on and says why.
- F4: calibration stored as atoms round-trips through `omg_atoms.py verify`.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-opus-5-5)
