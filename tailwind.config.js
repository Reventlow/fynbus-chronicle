/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        // Light mode earth tones - Scandinavian palette
        sand: {
          50: '#FAF9F7',
          100: '#F0EDE8',
          200: '#E5E0D8',
          300: '#D4CCC0',
          400: '#B8AC9A',
          500: '#A69076',
          600: '#8B7355',
          700: '#6B635B',
          800: '#4A4540',
          900: '#2C2825',
        },
        // Accent colors
        sage: {
          50: '#F4F6F3',
          100: '#E8EBE6',
          200: '#D1D7CC',
          300: '#B5BFAD',
          400: '#96A38B',
          500: '#7D8471',
          600: '#6B7260',
          700: '#565C4E',
          800: '#454A3F',
          900: '#3A3E35',
        },
        terracotta: {
          50: '#FBF5F4',
          100: '#F5E8E7',
          200: '#EDD5D3',
          300: '#DEB6B3',
          400: '#C98D89',
          500: '#A65D57',
          600: '#8B4D48',
          700: '#74403C',
          800: '#613835',
          900: '#533330',
        },
        gold: {
          50: '#FDFBF3',
          100: '#FAF5E1',
          200: '#F4E9C3',
          300: '#EBD89A',
          400: '#DFC36E',
          500: '#C4A35A',
          600: '#A68B4A',
          700: '#8A723E',
          800: '#725E38',
          900: '#5F4E31',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)',
        'soft-lg': '0 10px 40px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
