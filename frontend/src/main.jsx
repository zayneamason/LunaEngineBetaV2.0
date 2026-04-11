import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import 'katex/dist/katex.min.css'

// Apply stored formatting preset before first render to avoid flash
try {
  const root = document.documentElement.style;
  const s = localStorage.getItem('ec-font-scale');
  if (s) root.setProperty('--ec-font-scale', s);
  const lh = localStorage.getItem('ec-line-height');
  if (lh) root.setProperty('--ec-line-height', lh);
  const pg = localStorage.getItem('ec-paragraph-gap');
  if (pg) root.setProperty('--ec-paragraph-gap', pg);
} catch { /* ignore */ }

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
