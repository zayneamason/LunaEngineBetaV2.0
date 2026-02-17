/**
 * KOZMO — Entry Point
 *
 * Standalone: renders KOZMO as root app on :5174
 * Eclissi-hosted: Eclissi imports <KozmoApp /> and mounts it as a route
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import KozmoApp from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <KozmoApp />
  </React.StrictMode>
);
