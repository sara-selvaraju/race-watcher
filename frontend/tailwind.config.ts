import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "var(--ink)",
          deep: "var(--ink-deep)",
        },
        washi: {
          DEFAULT: "var(--washi)",
          raised: "var(--washi-raised)",
          glow: "var(--washi-glow)",
        },
        paper: {
          DEFAULT: "var(--paper)",
          dim: "var(--paper-dim)",
          faint: "var(--paper-faint)",
          ghost: "var(--paper-ghost)",
        },
        vermilion: {
          DEFAULT: "var(--vermilion)",
          deep: "var(--vermilion-deep)",
        },
        matcha: {
          DEFAULT: "var(--matcha)",
          deep: "var(--matcha-deep)",
        },
        gold: {
          DEFAULT: "var(--gold)",
          deep: "var(--gold-deep)",
        },
        indigo: { ink: "var(--indigo)" },
        hairline: {
          DEFAULT: "var(--hairline)",
          bright: "var(--hairline-bright)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        kanji: "0.3em",
        section: "0.25em",
      },
      borderRadius: {
        bento: "2px",
      },
    },
  },
  plugins: [],
};

export default config;
