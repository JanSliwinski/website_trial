import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        aegean: {
          950: "#07101D",
          900: "#0C1A2C",
          800: "#112236",
          700: "#173353",
          600: "#1E3D64",
          500: "#2A527F",
        },
        gold: {
          700: "#9A7A1A",
          600: "#B8941F",
          500: "#C8A84B",
          400: "#DFC060",
          300: "#F0DA90",
        },
        azure: {
          700: "#2A5580",
          600: "#3A6A9A",
          500: "#4A7FB5",
          400: "#6B99CC",
          300: "#8CB4DE",
        },
        marble: {
          50:  "#F8F5EE",
          100: "#EDE8DC",
          200: "#D8D2C4",
          300: "#BDB5A6",
          400: "#9B9188",
          500: "#7A8FA8",
          600: "#5A6E82",
        },
        olive: {
          600: "#3A8A60",
          500: "#4CAF82",
          400: "#6DC49A",
        },
        terra: {
          600: "#A84528",
          500: "#C4533A",
          400: "#D4705A",
        },
      },
      animation: {
        "fade-up": "fadeUp 0.4s ease-out",
        "fade-in": "fadeIn 0.3s ease-out",
      },
      keyframes: {
        fadeUp: {
          "0%":   { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
