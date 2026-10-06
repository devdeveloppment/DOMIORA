/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js"
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Montserrat', 'sans-serif'],
      },
      colors: {
        primary: {
          50: '#fdf3f4',
          100: '#f9e3e7',
          200: '#f2cbd3',
          300: '#e7a5b3',
          400: '#c24962',
          500: '#71212d',
          600: '#5a1a24',
          700: '#43131b',
          800: '#371116',
          900: '#2d0c12',
          950: '#170609'
        },
        accent: {
          50: '#fff8e6',
          100: '#fff1cc',
          200: '#ffe39a',
          300: '#ffd568',
          400: '#eec735',
          500: '#d4af37',
          600: '#b8860b',
          700: '#9c6a09'
        },
        ink: '#0f172a'
      },
      boxShadow: {
        card: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.06)',
        glow: '0 0 0 1px rgba(113,33,45,.15), 0 8px 24px -4px rgba(113,33,45,.25)'
      },
      borderRadius: {
        DEFAULT: '0.75rem',
        lg: '1rem',
        xl: '1.5rem'
      }
    }
  },
  plugins: []
}