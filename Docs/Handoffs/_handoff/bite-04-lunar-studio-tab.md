# Bite 4 — Lunar Studio Tab

The Lunar Studio tab in `EclissiShell.jsx` currently renders sub-tabs with `PipelineView.jsx` and `ExpressionView.jsx` that you created in a prior session. These duplicate functionality that already exists in the standalone Studio app at `/studio/`.

## What to do

1. Delete `frontend/src/eclissi/PipelineView.jsx`
2. Delete `frontend/src/eclissi/ExpressionView.jsx`
3. In `EclissiShell.jsx`, replace the entire `{activeTab === 'studio' && (...)}` block with a single iframe:

```jsx
{activeTab === 'studio' && (
  <iframe
    src="/studio/"
    style={{
      width: '100%',
      height: '100%',
      border: 'none',
      background: 'var(--ec-bg)',
    }}
    title="Lunar Studio"
  />
)}
```

4. Remove the `studioSub` state variable and the sub-tab bar code
5. Remove the PipelineView and ExpressionView imports
6. Keep the QAModuleView import — we'll use it in bite 5

The `/studio/` URL is relative — the Vite proxy (bite 3) forwards it to the backend which serves the existing Engine Pipeline diagnostic app.

Do NOT build new components. Do NOT create new views. Just wire to what exists.
