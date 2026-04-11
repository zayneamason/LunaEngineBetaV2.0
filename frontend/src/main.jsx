import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import 'katex/dist/katex.min.css'

// Apply stored font scale before first render to avoid flash
try {
  const s = localStorage.getItem('ec-font-scale');
  if (s) document.documentElement.style.setProperty('--ec-font-scale', s);
} catch { /* ignore */ }

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
