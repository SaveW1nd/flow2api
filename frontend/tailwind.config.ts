import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 高端蓝色企业风配色
        ink: {
          950: "#050B1A",
          900: "#0A1228",
          800: "#0F1B38",
          700: "#16264C",
        },
        brand: {
          50: "#EAF2FF",
          100: "#D6E4FF",
          300: "#7DA8FF",
          400: "#4C82F7",
          500: "#2563EB",
          600: "#1D4FD8",
          700: "#1840B0",
        },
        cyanx: {
          400: "#22D3EE",
          500: "#06B6D4",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        none: "0",
        sm: "3px",
        DEFAULT: "4px",
        md: "5px",
        lg: "6px",
        xl: "7px",
        "2xl": "8px",
        "3xl": "10px",
        full: "9999px",
      },
      boxShadow: {
        glow: "0 0 18px -8px rgba(37,99,235,0.45)",
        card: "0 4px 20px -12px rgba(2,8,23,0.5)",
      },
      backgroundImage: {
        "grid-faint":
          "linear-gradient(to right, rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        floaty: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.8s infinite",
        floaty: "floaty 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
