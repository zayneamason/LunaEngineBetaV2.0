/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        display: ['"Space Grotesk"', 'sans-serif'],
      },
      colors: {
        kozmo: {
          bg: '#0a0a0f',
          surface: '#12121a',
          border: '#1e1e2e',
          muted: '#4a4a5a',
          accent: '#c084fc',     // Violet — KOZMO primary
          eden: '#34d399',       // Emerald — Eden/agent status
          warning: '#fbbf24',    // Amber — warnings
          danger: '#f87171',     // Red — errors
          cinema: '#818cf8',     // Indigo — camera/production
        },
      },
    },
  },
  plugins: [],
};
