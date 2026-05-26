import { Toaster as SonnerToaster } from "sonner";

/**
 * Project-wide toast container. Use `toast.success(...)`, `toast.error(...)`,
 * `toast.message(...)` from `sonner` anywhere in the app.
 */
export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      richColors
      closeButton
      expand
      gap={14}
      offset={{ bottom: "1.25rem", right: "1.25rem" }}
      visibleToasts={4}
      toastOptions={{
        classNames: {
          toast:
            "!font-sans !text-sm !border !border-border !shadow-lift !rounded-lg",
          title: "!text-ink !font-medium",
          description: "!text-muted",
        },
      }}
    />
  );
}
