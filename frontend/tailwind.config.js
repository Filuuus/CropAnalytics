/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx,html}"],
  theme: {
    extend: {
      colors: {
        "color-white-solid": "#fff",
        "color-grey-98": "#f8fafc",
        "color-grey-91": "#e5e7eb",
        "color-azure-11": "#111827",
        "color-azure-27": "#374151",
        "color-azure-53": "#2563eb",
        "color-azure-34": "#4b5563",
        "color-grey-97": "#eff6ff",
        "color-grey-46-30": "rgba(107, 114, 128, 0.3)",
        "color-grey-46": "#6b7280",
        "color-white-90": "rgba(255, 255, 255, 0.9)",
        "color-azure-65": "#9ca3af",
        "color-spring-green-45": "#22c55e",
        "color-azure-60": "#3b82f6",
        "color-azure-5": "#020817",
        "color-azure-47": "#64748b",
        "color-grey-93": "#dcfce7",
        "color-blue-40": "#1e40af",
        "color-spring-green-24": "#166534",
        "color-black-solid": "#000",
        "color-spring-green-39": "#10b981",
        "color-spring-green-36": "#16a34a",
        "color-black-0": "rgba(0, 0, 0, 0)",
        "color-azure-84": "#d1d5db",
        "484758-aaf9575caf49488797eefed1c1b197ed-3-latestappmgxdev-athens-gray":
          "#e5e7eb",
        "484758-aaf9575caf49488797eefed1c1b197ed-3-latestappmgxdev-mystic":
          "#e5e7eb",
        "484758-aaf9575caf49488797eefed1c1b197ed-3-latestappmgxdev-mystic1":
          "#e5e7eb",
        "484758-aaf9575caf49488797eefed1c1b197ed-3-latestappmgxdev-white":
          "#fff",
      },
      spacing: {
        "height-1200": "1200px",
        "item-spacing-233-2": "233.2px",
        "item-spacing-xs": "8px",
        "item-spacing-m": "32px",
        "width-1280": "1280px",
        "item-spacing-s": "24px",
        "item-spacing-4": "4px",
        "item-spacing-12": "12px",
        "item-spacing-s1": "16px",
        "item-spacing-549-17": "549.17px",
        "item-spacing-171-95": "171.95px",
        "item-spacing-137-75": "137.75px",
        "item-spacing-426-46": "426.46px",
        "item-spacing-431-14": "431.14px",
        "item-spacing-425-61": "425.61px",
        "item-spacing-790-95": "790.95px",
        "item-spacing-1": "-1px",
        "width-768": "768px",
        "item-spacing-xl": "64px",
        "width-672": "672px",
      },
      fontFamily: {
        "font-family-font-1": "Inter",
      },
      borderWidth: {
        "stroke-weight-1": "1px",
      },
      opacity: {
        "opacity-100": "1",
        "opacity-50": "0.5",
      },
    },
    fontSize: {
      "font-size-20-93": "1.308rem",
      "font-size-13-44": "0.84rem",
      "font-size-12": "0.75rem",
      "font-size-16": "1rem",
      "font-size-14": "0.875rem",
    },
    fontWeight: {
      "font-weight-700": "700",
      "font-weight-400": "400",
    },
    lineHeight: {
      "line-height-28": "28px",
      "line-height-20": "20px",
      "line-height-36": "36px",
      "line-height-24": "24px",
      "line-height-16": "16px",
      "line-height-60": "60px",
      "line-height-32-5": "32.5px",
      "line-height-22-75": "22.75px",
    },
    letterSpacing: {
      "letter-spacing-0-6": "-0.6px",
    },
    screens: {
      lg: {
        raw: "screen and (max-width: 1200px)",
      },
    },
  },
  corePlugins: {
    preflight: false,
  },
};
