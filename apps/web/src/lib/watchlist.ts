/**
 * Curated keyword library shared between the CategoryPicker (Watchlist
 * section at top of the dropdown) and the KeywordPicker (Suggestions
 * popover). Sourced from the BD team's tracking brief.
 *
 * Single source of truth — update here, both surfaces reflect the change.
 */
export interface WatchlistGroup {
  label: string;
  hint?: string;
  items: string[];
}

export const WATCHLIST: WatchlistGroup[] = [
  {
    label: "Categories",
    hint: "Broad areas to monitor",
    items: [
      "nutraceuticals",
      "nootropics",
      "supplements",
      "ANDS",
      "smoking cessation",
    ],
  },
  {
    label: "Products & themes",
    hint: "Specific formats and form-factors",
    items: [
      "sublingual strip",
      "vapor technology",
      "adaptogen gummies",
      "functional mushrooms",
      "mood modulation",
      "nutraceutical aerosol",
      "pulmonary inhalation",
      "nootropic pouches",
    ],
  },
  {
    label: "Brands",
    hint: "Companies to track",
    items: ["ULTRA Pouches", "Stay Wyld", "Stay Wyld Functional Mushrooms", "Nectr"],
  },
];
