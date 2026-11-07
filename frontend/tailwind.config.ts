import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ground: "var(--ground)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        line: "var(--line)",
        brand: { DEFAULT: "var(--brand)", dark: "var(--brand-dark)", tint: "var(--brand-tint)" },
        saffron: { DEFAULT: "var(--saffron)", tint: "var(--saffron-tint)", ink: "var(--saffron-ink)" },
        sos: { DEFAULT: "var(--sos)", dark: "var(--sos-dark)", tint: "var(--sos-tint)" },
        ok: { DEFAULT: "var(--ok)", tint: "var(--ok-tint)" },
      },
      fontFamily: {
        sans: ["Atkinson Hyperlegible", "Noto Sans Devanagari", "Noto Sans Kannada", "Noto Sans Telugu", "system-ui", "sans-serif"],
      },
      fontSize: {
        // scalable with the user's text-size control via --scale
        base: ["calc(1.125rem * var(--scale))", { lineHeight: "1.6" }],
        sm: ["calc(1rem * var(--scale))", { lineHeight: "1.5" }],
        xs: ["calc(0.9rem * var(--scale))", { lineHeight: "1.45" }],
        lg: ["calc(1.35rem * var(--scale))", { lineHeight: "1.4" }],
        xl: ["calc(1.65rem * var(--scale))", { lineHeight: "1.3" }],
        "2xl": ["calc(2.05rem * var(--scale))", { lineHeight: "1.2" }],
        "3xl": ["calc(2.6rem * var(--scale))", { lineHeight: "1.1" }],
      },
      borderRadius: { xl: "14px", "2xl": "22px" },
    },
  },
  plugins: [],
};
export default config;
