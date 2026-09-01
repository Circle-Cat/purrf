# Prototypes

Standalone HTML prototypes. Open the file in a browser — no build step, no dev server.

These are design artefacts, not application code. They are deliberately plain HTML so they stay
openable years from now, and they are not imported by anything under `src/`.

## Keeping them honest

Each prototype copies its colour tokens **verbatim** from `frontend/src/index.css`. Never hand-tune
a colour inside a prototype: if a value looks wrong, the app is where it changes, and the prototype
follows. Anything a prototype invents beyond those tokens is called out in a comment where it is
defined.

## Contents

| File | What it shows |
|---|---|
| `scorm-training.html` | SCORM training: course list, package upload, trial run, assignment, the learner's profile section, and the learning page. Six views with a state switcher for the variants that matter (validation outcomes, trial-run verdicts, learner failure states). |

Design decisions and the redlines behind them live in
`docs/superpowers/specs/2026-08-28-scorm-training-design.md`.
