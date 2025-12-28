/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#014491',
          light: '#2A6DB8',
          dark: '#002A5E',
        },
        secondary: {
          DEFAULT: '#1A73E8',
        },
      },
    },
  },
  plugins: [],
};