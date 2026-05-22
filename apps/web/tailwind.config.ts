import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1A1A1A",
        navy: "#0B2A4A",
        accent: "#C85A1A",
        muted: "#666A70",
        soft: "#9A9FA5",
        tint: "#F5F2EE",
        border: "#EAE5DE",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)",
        lift: "0 8px 24px -8px rgba(16, 24, 40, 0.12), 0 2px 6px rgba(16, 24, 40, 0.04)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(200, 90, 26, 0.5)" },
          "70%": { boxShadow: "0 0 0 8px rgba(200, 90, 26, 0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(200, 90, 26, 0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 220ms ease-out",
        shimmer: "shimmer 1.8s linear infinite",
        "pulse-ring": "pulse-ring 1.6s ease-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
