/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/renderer/index.html', './src/renderer/src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        coral: {
          DEFAULT: '#FF6B5A',
          50: '#FFF1EF',
          100: '#FFE1DD',
          200: '#FFC3BB',
          300: '#FFA599',
          400: '#FF8777',
          500: '#FF6B5A',
          600: '#F2432E',
          700: '#C93221',
          800: '#9B2718',
          900: '#6E1B11'
        },
        teal: {
          DEFAULT: '#2BBBAD',
          50: '#EAFBF9',
          100: '#D0F5F1',
          200: '#A3ECE3',
          300: '#75E2D5',
          400: '#4CD1C2',
          500: '#2BBBAD',
          600: '#219A8F',
          700: '#1A7A71',
          800: '#145A54',
          900: '#0D3B37'
        },
        ink: {
          50: '#F8F9FA',
          100: '#F1F3F5',
          200: '#E9ECEF',
          300: '#DEE2E6',
          400: '#CED4DA',
          500: '#ADB5BD',
          600: '#868E96',
          700: '#495057',
          800: '#343A40',
          900: '#212529'
        }
      },
      fontFamily: {
        khmer: ['"Kantumruy Pro"', '"Khmer OS"', 'sans-serif'],
        latin: ['Inter', '"Segoe UI"', 'sans-serif']
      },
      borderRadius: {
        card: '18px'
      },
      boxShadow: {
        card: '0 1px 2px rgba(33,37,41,0.04), 0 8px 24px rgba(33,37,41,0.06)',
        popover: '0 12px 32px rgba(33,37,41,0.14)'
      }
    }
  },
  plugins: []
}
