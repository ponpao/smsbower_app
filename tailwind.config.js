/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#0d1420', // app background
          900: '#111a2b',
          850: '#152036',
          800: '#1b2740',
          700: '#26324f',
        },
        accent: {
          DEFAULT: '#3b82f6',
          soft: '#60a5fa',
          dim: '#1e3a8a',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
