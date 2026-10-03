import { PageShell } from "@/components/workspace/page-shell";
import { loading } from "@/lib/copy";

const bar = (width: string, height: string) => ({ width, height, display: "block", maxWidth: "100%" });

/**
 * Route loading state (used by loading.tsx). It keeps the shell on screen and reserves
 * roughly the space of a page header and its first cards, so navigation answers at once
 * and the content that replaces it does not jump.
 */
export default function PageSkeleton() {
  return (
    <PageShell>
      <div className="route-skeleton" role="status" aria-live="polite">
        <span className="sr-only">{loading.space.note}</span>
        <div aria-hidden="true" style={{ display: "grid", gap: "0.75rem", marginBottom: "2rem" }}>
          <span className="skeleton" style={bar("7rem", "0.75rem")} />
          <span className="skeleton" style={bar("20rem", "2.25rem")} />
          <span className="skeleton" style={bar("32rem", "1rem")} />
        </div>
        <div aria-hidden="true" style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))" }}>
          <span className="skeleton" style={bar("100%", "9rem")} />
          <span className="skeleton" style={bar("100%", "9rem")} />
          <span className="skeleton" style={bar("100%", "9rem")} />
        </div>
      </div>
    </PageShell>
  );
}
