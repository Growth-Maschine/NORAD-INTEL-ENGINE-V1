import { NavLink } from "react-router-dom";
import {
  Building2,
  ChevronsLeft,
  ChevronsRight,
  Compass,
  LayoutDashboard,
  Radio,
  Rss,
  Settings,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { HoverTip } from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils";
import {
  useCloseOnNavigate,
  useMobileMenu,
} from "./mobile-menu-context";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  soon?: boolean;
}

const PRIMARY: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/discover", label: "Today", icon: Compass },
  { to: "/companies", label: "Companies", icon: Building2 },
];

const PHASE_2: NavItem[] = [
  { to: "/signals", label: "Signals", icon: Radio, soon: true },
  { to: "/feeds", label: "Feeds", icon: Rss, soon: true },
];

const FOOTER: NavItem[] = [{ to: "/settings", label: "Settings", icon: Settings }];

const COLLAPSE_KEY = "norad.sidebar.collapsed";

function loadCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

export function Sidebar() {
  const { open, close } = useMobileMenu();
  useCloseOnNavigate();

  const [collapsed, setCollapsed] = useState<boolean>(loadCollapsed);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  // Mobile drawer always shows full sidebar — collapse is a desktop concept.
  return (
    <>
      {/* Mobile backdrop */}
      <div
        onClick={close}
        aria-hidden
        className={cn(
          "fixed inset-0 z-30 bg-black/40 backdrop-blur-sm transition-opacity md:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        className={cn(
          "flex h-screen shrink-0 flex-col bg-navy text-white",
          // Width animates between collapsed (rail) and expanded.
          "transition-[width] duration-200 ease-out",
          // Mobile is always full-width drawer
          "fixed inset-y-0 left-0 z-40 w-60 -translate-x-full md:static md:translate-x-0",
          "transition-transform duration-200 ease-out",
          open && "translate-x-0 shadow-lift",
          collapsed ? "md:w-[68px]" : "md:w-60",
        )}
        aria-label="Primary navigation"
      >
        {/* Brand */}
        <div
          className={cn(
            "flex h-16 shrink-0 items-center gap-3 border-b border-white/10",
            collapsed ? "md:justify-center md:px-2 px-5" : "px-5",
          )}
        >
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-accent text-xs font-bold tracking-wider shadow-soft">
            N
          </div>
          <div
            className={cn(
              "flex flex-1 flex-col leading-tight overflow-hidden transition-opacity",
              collapsed ? "md:hidden" : "opacity-100",
            )}
          >
            <span className="text-sm font-semibold tracking-wide">NORAD</span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-white/50">
              Intel Engine
            </span>
          </div>
          {/* Mobile close button */}
          <button
            type="button"
            onClick={close}
            className="grid h-8 w-8 place-items-center rounded-md text-white/60 transition hover:bg-white/10 hover:text-white md:hidden"
            aria-label="Close menu"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="scrollbar-dark min-h-0 flex-1 overflow-y-auto px-3 py-5">
          <SectionLabel collapsed={collapsed}>Workspace</SectionLabel>
          <ul className={cn("space-y-0.5", collapsed ? "mt-1" : "mt-2")}>
            {PRIMARY.map((item) => (
              <NavRow key={item.to} item={item} collapsed={collapsed} />
            ))}
          </ul>

          <SectionLabel collapsed={collapsed} className={collapsed ? "mt-4" : "mt-7"}>
            Trend Hunter
          </SectionLabel>
          <ul className={cn("space-y-0.5", collapsed ? "mt-1" : "mt-2")}>
            {PHASE_2.map((item) => (
              <NavRow key={item.to} item={item} collapsed={collapsed} />
            ))}
          </ul>
        </nav>

        {/* Footer */}
        <div className="shrink-0 border-t border-white/10 px-3 py-3">
          <ul className="space-y-0.5">
            {FOOTER.map((item) => (
              <NavRow key={item.to} item={item} collapsed={collapsed} />
            ))}
          </ul>

          {/* Collapse toggle (desktop only) — icon only, sits inline with the
              version row when expanded, centered when collapsed. */}
          {collapsed ? (
            <div className="mt-2 hidden md:block">
              <HoverTip label="Expand sidebar" side="right">
                <button
                  type="button"
                  onClick={() => setCollapsed(false)}
                  aria-label="Expand sidebar"
                  aria-pressed={collapsed}
                  className="mx-auto flex h-8 w-8 items-center justify-center rounded-md text-white/50 transition-colors hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
                >
                  <ChevronsRight className="h-5 w-5" />
                </button>
              </HoverTip>
            </div>
          ) : (
            <div className="mt-2 hidden items-center justify-between gap-2 pl-3 pr-1 text-[10px] text-white/40 md:flex">
              <span>v0.1.0</span>
              <span>single-user</span>
              <HoverTip label="Collapse sidebar" side="top">
                <button
                  type="button"
                  onClick={() => setCollapsed(true)}
                  aria-label="Collapse sidebar"
                  aria-pressed={collapsed}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-white/50 transition-colors hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
                >
                  <ChevronsLeft className="h-4 w-4" />
                </button>
              </HoverTip>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

function SectionLabel({
  children,
  className,
  collapsed,
}: {
  children: React.ReactNode;
  className?: string;
  collapsed: boolean;
}) {
  if (collapsed) {
    // In collapsed mode we render a hairline divider instead of a label,
    // so the rail stays icon-only and visually grouped.
    return (
      <div
        aria-hidden
        className={cn("mx-3 h-px bg-white/10", className)}
      />
    );
  }
  return (
    <div
      className={cn(
        "px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/40",
        className,
      )}
    >
      {children}
    </div>
  );
}

function NavRow({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = item.icon;

  if (item.soon) {
    const content = (
      <span
        aria-disabled="true"
        className={cn(
          "flex cursor-not-allowed items-center gap-3 rounded-md py-2 text-sm text-white/40",
          collapsed ? "justify-center px-2" : "px-3",
        )}
      >
        <Icon className="h-5 w-5 shrink-0" />
        {!collapsed && (
          <>
            <span className="flex-1">{item.label}</span>
            <span className="rounded-sm bg-white/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-white/60">
              Soon
            </span>
          </>
        )}
      </span>
    );

    return (
      <li>
        {collapsed ? (
          <HoverTip label={`${item.label} — coming soon`} side="right">
            {/* span as tooltip trigger — needs to be focusable */}
            <span tabIndex={0} className="block focus-visible:outline-none">
              {content}
            </span>
          </HoverTip>
        ) : (
          content
        )}
      </li>
    );
  }

  const link = (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      className={({ isActive }) =>
        cn(
          "group relative flex items-center gap-3 rounded-md py-2 text-sm transition-colors",
          "text-white/70 hover:bg-white/5 hover:text-white",
          isActive && "bg-white/10 text-white",
          collapsed ? "justify-center px-2" : "px-3",
        )
      }
    >
      {({ isActive }) => (
        <>
          {/* Active accent bar */}
          <span
            aria-hidden
            className={cn(
              "absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-accent transition-opacity",
              isActive ? "opacity-100" : "opacity-0",
            )}
          />
          <Icon
            className={cn(
              "h-5 w-5 shrink-0 transition-colors",
              isActive ? "text-accent" : "text-white/60 group-hover:text-white",
            )}
          />
          {!collapsed && <span className="flex-1">{item.label}</span>}
        </>
      )}
    </NavLink>
  );

  return (
    <li>
      {collapsed ? (
        <HoverTip label={item.label} side="right">
          {link}
        </HoverTip>
      ) : (
        link
      )}
    </li>
  );
}
