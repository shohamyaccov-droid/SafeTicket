/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        bloomfield: {
          available: '#a3e635',
          pitch: '#4ade80',
          pitchDark: '#16a34a',
        },
      },
    },
  },
  plugins: [],
};
