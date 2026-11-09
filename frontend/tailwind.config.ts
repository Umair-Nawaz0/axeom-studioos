import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      colors: {
        canvas: "var(--app-bg)",
        surface: {
          DEFAULT: "var(--surface)",
          muted: "var(--surface-muted)",
          hover: "var(--surface-hover)",
        },
        sidebar: {
          bg: "var(--sidebar-bg)",
          text: "var(--sidebar-text)",
          muted: "var(--sidebar-muted)",
        },
        border: {
          DEFAULT: "var(--border)",
          subtle: "var(--border-subtle)",
        },
        brand: {
          DEFAULT: "var(--brand)",
          hover: "var(--brand-hover)",
          soft: "var(--brand-soft)",
        },
        ink: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        status: {
          warning: "var(--warning)",
          "warning-bg": "var(--warning-bg)",
          "warning-border": "var(--warning-border)",
          critical: "var(--critical)",
          "critical-bg": "var(--critical-bg)",
          "critical-border": "var(--critical-border)",
          success: "var(--success)",
          "success-bg": "var(--success-bg)",
          "success-border": "var(--success-border)",
          info: "var(--info)",
          "info-bg": "var(--info-bg)",
          "info-border": "var(--info-border)",
        },
      },
    },
  },
  plugins: [],
};
export default config;
