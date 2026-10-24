import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: {
          DEFAULT: "var(--surface)",
          2: "var(--surface-2)",
        },
        line: {
          DEFAULT: "var(--line)",
          strong: "var(--line-strong)",
        },
        ink: {
          DEFAULT: "var(--ink)",
          2: "var(--ink-2)",
          3: "var(--ink-3)",
        },
        turf: {
          DEFAULT: "var(--turf)",
          deep: "var(--turf-deep)",
          soft: "var(--turf-soft)",
        },
        silk: "var(--silk)",
        firm: "var(--firm)",
        drift: "var(--drift)",
      },
      fontFamily: {
        display: ["var(--font-display)", "Arial Narrow", "sans-serif"],
        sans: ["var(--font-sans)", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
