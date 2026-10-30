import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bloodstone: {
          canvas: "#041208",
          moss: "#0d3819",
          emerald: "#146132",
          crimson: "#b32424",
          "crimson-glow": "rgba(179, 36, 36, 0.75)",
          mint: "#7bf0a7",
          "mint-subtle": "rgba(123, 240, 167, 0.35)",
          text: "#e2f7eb",
          "text-muted": "#8ebca0",
          "dark-border": "rgba(4, 18, 8, 0.6)",
        },
      },
      backgroundColor: {
        "glass-base": "rgba(13, 56, 25, 0.45)",
        "glass-elevated": "rgba(13, 56, 25, 0.70)",
        "glass-crimson": "rgba(179, 36, 36, 0.75)",
        "glass-emerald": "rgba(20, 97, 50, 0.50)",
      },
      borderColor: {
        "glass-specular": "rgba(123, 240, 167, 0.35)",
        "glass-dark": "rgba(4, 18, 8, 0.60)",
        "glass-subtle": "rgba(123, 240, 167, 0.15)",
        "glass-crimson": "rgba(179, 36, 36, 0.50)",
      },
      boxShadow: {
        "bloodstone-glass": "inset 0 1px 1px 0 rgba(123, 240, 167, 0.3), 0 20px 40px -15px rgba(4, 18, 8, 0.7)",
        "bloodstone-glow": "0 0 25px rgba(20, 97, 50, 0.25), inset 0 1px 1px rgba(123, 240, 167, 0.35)",
        "crimson-glow": "0 0 25px rgba(179, 36, 36, 0.35), inset 0 1px 1px rgba(255, 120, 120, 0.4)",
        "specular-inset": "inset 0 1px 1px 0 rgba(123, 240, 167, 0.35)",
      },
      backdropBlur: {
        glass: "20px",
      },
      transitionDuration: {
        micro: "90ms",
        fast: "160ms",
        normal: "240ms",
        slow: "320ms",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
        settle: "cubic-bezier(0.25, 1, 0.5, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
