# 🌸 Whimsical To-Do

A desktop to-do list app with a twist: click the **MAGIC** button and a
tiny frameless popup opens showing a live countdown to your nearest
deadline, set against a hand-drawn flower scene. While it counts down,
a little roaming creature periodically floats across your screen with
a speech bubble reminding you how much time is left — and gets more
frequent the closer you get to the deadline.

Built with **Python** and **PySide6** (Qt for Python).

**⬇️ Download and run it:** see the [Releases page](../../releases/latest)
— grab `main.exe`, no Python or setup required (Windows only).

---

## Features

- **Task list** — add tasks with a name and a deadline time; check
  them off (with a real strikethrough) or delete them.
- **Magic popup** — a custom, frameless window with its own
  hand-drawn frame, title bar, and close/minimize buttons.
- **Live countdown** — ticks down to your soonest upcoming deadline,
  set against one of four flower-scene backgrounds that cycle based
  on each task's position in your list.
- **Roaming reminder creature** — a transparent, always-on-top
  floating window with a speech bubble showing time remaining. Drifts
  smoothly around the screen and dismisses on click.
- **Smart reminder timing** — pings at guaranteed 45/30/15-minute
  checkpoints as a deadline approaches, and every 30 minutes if it's
  still more than an hour out.

## How it was built

This started as a single detailed prompt describing the concept, UI
layout, and a set of 17 hand-drawn PNG assets, refined over several
rounds of feedback. The build process:

1. **Architecture** — split into four modules: `tasks.py` (plain data
   model), `main.py` (main window + task list), `popup.py` (the
   frameless countdown popup), and `creature.py` (the floating
   reminder). Each is independent and only talks to the others through
   simple callbacks and Qt signals.
2. **Custom-painted UI** — rather than relying on default OS window
   chrome, most of the interface is hand-painted with `QPainter`
   directly from the provided artwork, using frameless/translucent
   window flags to get the borderless, floating-creature look.
3. **Iterative refinement** — the popup flow, font choices, layout
   spacing, reminder cadence, and completed-task styling were all
   adjusted over multiple passes based on real feedback and testing.
4. **Packaging** — bundled into a standalone Windows `.exe` with
   PyInstaller and published as a GitHub Release, so it can be run by
   anyone without installing Python.

## Running from source

```bash
git clone https://github.com/drishti200301/whimsical-todo.git
cd whimsical-todo

python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
python main.py
```

## Project layout

```
whimsical-todo/
├── main.py          # entry point + main to-do window
├── popup.py         # the frameless "magic" countdown popup
├── creature.py       # the floating reminder creature
├── tasks.py         # plain Task data class (no UI code)
├── assets/          # PNG artwork
├── requirements.txt
└── .gitignore
```

## Tech notes

- **`popup-panel.png`** was supplied as 280×220 (landscape); it's
  rotated 90° in code to match the 220×280 portrait frame the rest of
  the design (titlebar, flower scenes) is built around.
- Reminder frequency and countdown logic live entirely in `main.py`
  and `popup.py`, decoupled via Qt signals — `popup.py` has no idea
  how tasks are stored, it just asks `main.py` for "the active task"
  through a callback.
