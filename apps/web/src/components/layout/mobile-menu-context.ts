import { createContext, useContext, useEffect } from "react";

export interface MobileMenuValue {
  open: boolean;
  toggle: () => void;
  close: () => void;
  locationKey: string;
}

export const MobileMenuContext = createContext<MobileMenuValue | null>(null);

export function useMobileMenu(): MobileMenuValue {
  const ctx = useContext(MobileMenuContext);
  if (!ctx) {
    throw new Error("useMobileMenu must be used inside <AppShell>");
  }
  return ctx;
}

/** Auto-close the drawer whenever the route changes. */
export function useCloseOnNavigate() {
  const { close, locationKey } = useMobileMenu();
  useEffect(() => {
    close();
  }, [locationKey, close]);
}
