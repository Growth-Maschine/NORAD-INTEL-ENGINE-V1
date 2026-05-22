import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { TooltipProvider } from "@radix-ui/react-tooltip";

import { Sidebar } from "./Sidebar";
import { MobileMenuContext } from "./mobile-menu-context";
import { Toaster } from "@/components/ui/Toaster";

/**
 * Top-level app chrome: persistent sidebar on desktop, off-canvas drawer on
 * mobile. Mobile-menu open state lives here and is exposed via context so
 * any descendant (Topbar's hamburger, Sidebar's close button) can drive it
 * without prop drilling. The Sidebar uses `useCloseOnNavigate` to auto-close
 * the drawer on every route change.
 *
 * Also mounts the global Sonner Toaster and Radix TooltipProvider so any
 * component can `toast.success(...)` or use <HoverTip> without extra setup.
 */
export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  return (
    <MobileMenuContext.Provider
      value={{
        open: mobileOpen,
        toggle: () => setMobileOpen((v) => !v),
        close: () => setMobileOpen(false),
        locationKey: location.key,
      }}
    >
      <TooltipProvider delayDuration={250} skipDelayDuration={100}>
        <div className="flex h-screen w-full bg-tint/30 text-ink">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Outlet />
          </div>
        </div>
        <Toaster />
      </TooltipProvider>
    </MobileMenuContext.Provider>
  );
}
