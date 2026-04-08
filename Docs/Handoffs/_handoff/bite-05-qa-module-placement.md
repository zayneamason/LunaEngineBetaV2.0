# Bite 5 — QA Module Placement

The QA module (`QAModuleView.jsx`) exists and works but needs a home now that Lunar Studio is an iframe.

## What to do

Add a "QA" tab to the existing standalone Studio app — the one at `Tools/Luna-Expression-Pipeline/diagnostic/`. This app already has tabs (Expression, Engine Pipeline, Nexus). QA becomes a fourth tab.

Two approaches (pick whichever is cleaner):

### Option A: Add QA tab to the standalone Studio app
- The Studio app is a built React app in `Tools/Luna-Expression-Pipeline/diagnostic/`
- Add a QA tab that fetches from `/api/diagnostics/qa/health`, `/qa/health`, etc.
- Render the 4-panel layout (Monitor, Health, Assertions, Bugs) from `QAModuleView.jsx`

### Option B: Keep QA in Eclissi as a separate top-level tab
- If wiring into the standalone app is too complex, keep `QAModuleView` accessible from the Eclissi shell as its own tab (not a sub-tab of Studio)
- Add it to the TABS array and render it directly

Either way, the QA diagnostic workspace must be accessible. Pick the path of least resistance.

Do this and nothing else.
