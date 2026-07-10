/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f172a",
          elevated: "#1e293b",
          border: "#334155",
        },
        accent: {
          DEFAULT: "#3b82f6",
          muted: "#1d4ed8",
        },
      },
    },
  },
  plugins: [],
};
