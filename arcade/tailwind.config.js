/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'arcade-bg':      '#0D0221',
        'arcade-surface': '#1A0A3E',
        'arcade-border':  '#2D1B69',
        'arcade-cyan':    '#00F5FF',
        'arcade-magenta': '#FF00AA',
        'arcade-gold':    '#FFD700',
        'arcade-silver':  '#C0C0C0',
        'arcade-bronze':  '#CD7F32',
        'arcade-danger':  '#FF3366',
        'arcade-muted':   '#6B5B95',
      },
      fontFamily: {
        pixel: ['"Press Start 2P"', 'monospace'],
        body:  ['"Space Grotesk"', 'sans-serif'],
      },
      animation: {
        'breathe':     'breathe 4s ease-in-out infinite',
        'glow-pulse':  'glow-pulse 2s ease-in-out infinite',
        'float':       'float 6s ease-in-out infinite',
        'type-cursor': 'type-cursor 1s step-end infinite',
        'twinkle':     'twinkle 3s ease-in-out infinite',
        'fade-in':     'fade-in 0.5s ease-out',
        'count-up':    'count-up 2s ease-out',
      },
      keyframes: {
        breathe: {
          '0%, 100%': { transform: 'scale(1)', opacity: '1' },
          '50%':      { transform: 'scale(1.05)', opacity: '0.9' },
        },
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(0, 245, 255, 0.3)' },
          '50%':      { boxShadow: '0 0 40px rgba(0, 245, 255, 0.6)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%':      { transform: 'translateY(-8px)' },
        },
        'type-cursor': {
          '0%, 100%': { borderColor: 'transparent' },
          '50%':      { borderColor: '#00F5FF' },
        },
        twinkle: {
          '0%, 100%': { opacity: '0.3' },
          '50%':      { opacity: '1' },
        },
        'fade-in': {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
