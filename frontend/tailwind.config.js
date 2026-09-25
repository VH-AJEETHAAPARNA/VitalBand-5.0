/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          navy: "#0b2545",
          red: "#d92b2b",
          green: "#1e8e3e",
        },
      },
    },
  },
  plugins: [],
};
