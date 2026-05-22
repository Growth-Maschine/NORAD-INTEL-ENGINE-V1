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
      gap={12}
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
