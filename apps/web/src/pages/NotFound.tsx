import { Link } from "react-router-dom";
import { Compass } from "lucide-react";

import { Topbar } from "@/components/layout/Topbar";
import { PageBody } from "@/components/ui/PageBody";

export default function NotFound() {
  return (
    <>
      <Topbar title="Not found" />
      <PageBody>
        <div className="rounded-lg border border-border bg-white px-6 py-16 text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-tint">
            <Compass className="h-5 w-5 text-muted" />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-ink">
            That route doesn't exist
          </h2>
          <p className="mt-1 text-sm text-muted">
            Head back home and pick something from the sidebar.
          </p>
          <Link
            to="/"
            className="mt-5 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent/90"
          >
            Go home
          </Link>
        </div>
      </PageBody>
    </>
  );
}
