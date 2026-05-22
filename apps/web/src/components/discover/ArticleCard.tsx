import { motion } from "framer-motion";
import {
  ArrowUpRight,
  Building2,
  Calendar,
  ChevronDown,
  ChevronUp,
  Loader2,
  Target,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { HoverTip } from "@/components/ui/Tooltip";
import { Article } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Article card for the Today grid. Shows category + score, title, a
 * collapsible summary, the subject company(ies), and a quiet open-source
 * affordance. The big "Research" CTA lives *outside* the card — see
 * `ResearchTrigger.tsx` — so the card stays as a calm reading surface.
 */
export function ArticleCard({ article }: { article: Article }) {
  const [expanded, setExpanded] = useState(false);
  const score = article.relevance_score ?? 0;
  const scoreTone =
    score >= 80
      ? "success"
      : score >= 50
        ? "accent"
        : score > 0
          ? "warning"
          : "neutral";

  const isExtracted = article.status === "extracted";
  const primary = article.extracted_companies[0];

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cn(
        "group flex min-h-[360px] flex-col rounded-xl border border-border bg-white p-5 transition-all",
        "hover:-translate-y-0.5 hover:border-soft hover:shadow-lift",
      )}
    >
      <header className="mb-3 flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {article.category && (
            <Badge variant="navy" className="uppercase tracking-wider">
              {article.category}
            </Badge>
          )}
          {article.relevance_score != null && (
            <HoverTip
              label={
                article.relevance_reason ||
                "Relevance score — how well this signal matches BD intel."
              }
            >
              <button
                type="button"
                tabIndex={0}
                aria-label={`Relevance score: ${score} of 100`}
                className="cursor-help rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
              >
                <Badge variant={scoreTone}>
                  <Target className="h-3 w-3" /> {score}/100
                </Badge>
              </button>
            </HoverTip>
          )}
        </div>
        <HoverTip label="Open source on TrendHunter">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md p-1 text-soft transition hover:bg-tint hover:text-ink"
            aria-label="Open source"
          >
            <ArrowUpRight className="h-4 w-4" />
          </a>
        </HoverTip>
      </header>

      <h3 className="text-base font-semibold leading-snug text-ink">
        {article.title ?? article.url}
      </h3>

      {article.summary && (
        <>
          <p
            className={cn(
              "mt-2 text-sm leading-relaxed text-muted",
              !expanded && "line-clamp-4",
            )}
          >
            {article.summary}
          </p>
          {article.summary.length > 220 && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-1.5 inline-flex items-center gap-1 self-start text-[11px] font-medium text-accent transition hover:text-accent/80"
              aria-expanded={expanded}
            >
              {expanded ? (
                <>
                  Show less <ChevronUp className="h-3 w-3" />
                </>
              ) : (
                <>
                  Show more <ChevronDown className="h-3 w-3" />
                </>
              )}
            </button>
          )}
        </>
      )}

      {!article.summary && article.dek && (
        <>
          <p
            className={cn(
              "mt-2 text-sm italic leading-relaxed text-muted",
              !expanded && "line-clamp-3",
            )}
          >
            {article.dek}
          </p>
          {article.dek.length > 220 && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-1.5 inline-flex items-center gap-1 self-start text-[11px] font-medium text-accent transition hover:text-accent/80"
              aria-expanded={expanded}
            >
              {expanded ? (
                <>
                  Show less <ChevronUp className="h-3 w-3" />
                </>
              ) : (
                <>
                  Show more <ChevronDown className="h-3 w-3" />
                </>
              )}
            </button>
          )}
        </>
      )}

      {/* Subject company block — shown only when extraction complete.
          Index 0 is the *primary* subject (the maker / brand the product
          belongs to — this is also the one Profile research targets).
          Index 1+ are partners / mentioned brands, badged accordingly. */}
      {primary && (
        <div className="mt-4 rounded-lg border border-border bg-tint/30 p-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-soft">
            <Building2 className="h-3 w-3" /> Subject company
          </div>
          <ul className="space-y-2">
            {article.extracted_companies.slice(0, 2).map((c, i) => {
              const isPrimary = i === 0;
              return (
                <li key={i} className="flex items-start gap-3">
                  <div
                    className={cn(
                      "grid h-7 w-7 shrink-0 place-items-center rounded-md text-[10px] font-semibold uppercase",
                      isPrimary
                        ? "bg-accent/10 text-accent"
                        : "bg-slate-100 text-soft",
                    )}
                  >
                    {initials(c.name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={cn(
                          "truncate text-sm",
                          isPrimary
                            ? "font-semibold text-ink"
                            : "font-medium text-muted",
                        )}
                      >
                        {c.name}
                      </span>
                      <HoverTip
                        label={
                          isPrimary
                            ? "Primary subject — the brand this product belongs to. Profile research targets this company."
                            : "Mentioned alongside the primary brand (e.g. partner, collab, retailer)."
                        }
                      >
                        <span
                          tabIndex={0}
                          className={cn(
                            "shrink-0 cursor-help rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider",
                            isPrimary
                              ? "border-accent/30 bg-accent/10 text-accent"
                              : "border-border bg-white text-soft",
                          )}
                        >
                          {isPrimary ? "Primary" : "Partner"}
                        </span>
                      </HoverTip>
                    </div>
                    {c.excerpt && (
                      <HoverTip label={c.excerpt} side="bottom">
                        <button
                          type="button"
                          tabIndex={0}
                          aria-label={`Company excerpt: ${c.excerpt}`}
                          className="block w-full cursor-help rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
                        >
                          <p className="line-clamp-2 text-xs leading-relaxed text-muted">
                            {c.excerpt}
                          </p>
                        </button>
                      </HoverTip>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Ranked but not yet extracted → show a quiet processing state */}
      {!primary && isExtracted === false && article.status === "ranked" && (
        <div className="mt-4 inline-flex items-center gap-2 rounded-md bg-tint/40 px-2.5 py-1.5 text-xs text-muted">
          <Loader2 className="h-3 w-3 animate-spin text-accent" />
          Awaiting extraction…
        </div>
      )}

      <footer className="mt-auto flex items-center justify-between pt-4 text-[11px] text-soft">
        <span className="inline-flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          {article.published_date ?? "—"}
        </span>
        <Badge variant="outline" className="uppercase tracking-wider">
          {article.status}
        </Badge>
      </footer>
    </motion.article>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
