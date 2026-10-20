import type { Config } from "tailwindcss";

const v = (name: string) => `var(--${name})`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        ground: v("ground"),
        surface: v("surface"),
        raised: v("raised"),
        active: v("active"),
        line: v("border"),
        rule: v("rule"),
        control: v("control"),
        ink: v("text"),
        muted: v("muted"),
        faint: v("faint"),
        primary: v("primary"),
        "on-primary": v("on-primary"),
        accent: v("accent"),
        "accent-soft": v("accent-soft"),
        "accent-ink": v("accent-ink"),
        positive: v("positive"),
        negative: v("negative"),
        "pill-pos-bg": v("pill-positive-bg"),
        "pill-pos-ink": v("pill-positive-ink"),
        "pill-neg-bg": v("pill-negative-bg"),
        "pill-neg-ink": v("pill-negative-ink"),
        "pill-warn-bg": v("pill-warning-bg"),
        "pill-warn-ink": v("pill-warning-ink"),
        "pill-warn-line": v("pill-warning-line"),
      },
      fontFamily: { sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"] },
      fontSize: {
        meta: ["12px", "16px"],
        body: ["14px", "20px"],
        section: ["16px", "24px"],
        kpi: ["24px", "30px"],
        title: ["24px", "30px"],
        answer: ["36px", "40px"],
      },
      borderRadius: { card: "8px", control: "6px", chip: "4px" },
      maxWidth: { canvas: "1240px" },
    },
  },
  plugins: [],
} satisfies Config;
