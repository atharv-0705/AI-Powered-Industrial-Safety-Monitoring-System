/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        industrial: {
          bg: "#0B1220",
          sidebar: "#0F172A",
          card: "#111C2E",
          cardHover: "#162238",
          cardElevated: "#1A2840",
          border: "#25334A",
          borderLight: "#334460",
          textPrimary: "#F1F5F9",
          textSecondary: "#94A3B8",
          textMuted: "#64748B",
        },
        severity: {
          low: "#10B981",       // Compliant / Green
          medium: "#F59E0B",    // Caution / Amber
          high: "#F97316",      // Active Hazard / Orange
          critical: "#EF4444",  // Immediate Emergency / Red
          info: "#3B82F6",      // Blue / Info
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "Courier New", "monospace"],
      },
    },
  },
  plugins: [],
}

