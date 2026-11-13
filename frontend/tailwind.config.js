/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        sl: {
          maroon: "#8D153A",
          gold: "#FFBE29",
          orange: "#EB7400",
          teal: "#00534E",
          navy: "#0F172A",
        }
      }
    },
  },
  plugins: [],
};
