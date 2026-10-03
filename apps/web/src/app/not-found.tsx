import Link from "next/link";

import { shellCopy } from "@/lib/copy-shell";

const copy = shellCopy.notFound;

export default function NotFound() {
  return (
    <main id="main-content" className="status-page">
      <section>
        <h1 className="display">{copy.title}</h1>
        <p>{copy.body}</p>
        <div className="status-page-actions">
          <Link href="/dashboard" className="button-primary">{copy.home}</Link>
        </div>
      </section>
    </main>
  );
}
