/**
 * StrategicFitText
 * ────────────────
 * The Claude synthesizer routinely emits Strategic Fit summaries that pack a
 * lead paragraph + 2-4 enumerated action items inline as `(1) ... (2) ... (3)`.
 * Rendering that as one wall-of-prose <p> is unreadable.
 *
 * This component parses that exact pattern and renders:
 *   - the lead paragraph (everything before "(1)")
 *   - a numbered list where each item picks up its inline label
 *     ("Partnership opportunity:") as a bolded heading + the rest as body.
 *
 * If the text doesn't contain the (N) pattern, it falls back to a normal
 * paragraph render — non-destructive for cards that don't use the convention.
 */
import { cn } from "@/lib/utils";

type Item = {
  n: number;
  label: string | null;
  body: string;
};

/** Splits the strategic-fit text into a lead paragraph + numbered items.
 *  Matches `(1) `, `(1)`, `(10)`, etc. Anchored only at clear word boundaries
 *  so we don't accidentally split a parenthetical like "(1M cans)". */
function parse(text: string): { lead: string; items: Item[] } {
  // Require a space or end-of-string after the digit so "(1M cans)" doesn't
  // match — only true enumerators like "(1)" or "(1) ".
  const re = /\((\d{1,2})\)(?=\s)/g;
  const matches = [...text.matchAll(re)];
  if (matches.length < 2) {
    // Need at least two markers to call it an enumeration; otherwise treat
    // as plain prose.
    return { lead: text.trim(), items: [] };
  }

  const lead = text.slice(0, matches[0].index).trim();
  const items: Item[] = [];
  for (let i = 0; i < matches.length; i++) {
    const m = matches[i];
    const start = (m.index ?? 0) + m[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index ?? text.length : text.length;
    let chunk = text.slice(start, end).trim();
    // Drop a trailing semicolon that the synth often uses to chain items.
    chunk = chunk.replace(/[;,]\s*$/, "").trim();

    // Try to peel off a "Label: rest..." prefix. Label is up to ~50 chars,
    // starts with a letter, no internal sentence punctuation.
    let label: string | null = null;
    let body = chunk;
    const lm = chunk.match(/^([A-Z][^:.\n]{2,60}):\s*(.+)$/s);
    if (lm) {
      label = lm[1].trim();
      body = lm[2].trim();
    }
    items.push({ n: Number(m[1]), label, body });
  }
  return { lead, items };
}

export type StrategicFitTextProps = {
  text: string;
  /** Compact density — smaller font, tighter spacing. Used in list excerpts. */
  compact?: boolean;
  /** Optional className applied to the outer wrapper. */
  className?: string;
};

export function StrategicFitText({
  text,
  compact = false,
  className,
}: StrategicFitTextProps) {
  const { lead, items } = parse(text);

  const baseProse = compact
    ? "text-[13px] leading-relaxed text-muted"
    : "text-[14px] leading-[1.65] text-muted";

  return (
    <div className={cn("space-y-3", className)}>
      {lead && <p className={baseProse}>{lead}</p>}

      {items.length > 0 && (
        <ol
          className={cn(
            "space-y-2.5",
            compact && "space-y-2",
          )}
        >
          {items.map((it) => (
            <li
              key={it.n}
              className={cn(
                "flex gap-3 rounded-md border border-border/60 bg-tint/40 px-3 py-2.5",
                compact && "px-2.5 py-2",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent/10 text-[11px] font-semibold text-accent tabular-nums",
                  compact && "h-[18px] w-[18px] text-[10px]",
                )}
                aria-hidden
              >
                {it.n}
              </span>
              <div className="min-w-0 flex-1">
                {it.label && (
                  <div
                    className={cn(
                      "font-semibold text-ink",
                      compact ? "text-[12.5px]" : "text-[13.5px]",
                    )}
                  >
                    {it.label}
                  </div>
                )}
                <div
                  className={cn(
                    "text-muted",
                    compact ? "text-[12.5px] leading-relaxed" : "text-[13.5px] leading-[1.6]",
                    it.label && "mt-0.5",
                  )}
                >
                  {it.body}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
