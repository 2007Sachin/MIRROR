"use client"; // Error boundaries must be Client Components.

import Link from "next/link";

import { shellCopy } from "@/lib/copy-shell";

const copy = shellCopy.error;

/** Says what did not load and keeps the person on the same route, so Try again picks up where they were. */
export default function ErrorPage({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <main id="main-content" className="status-page">
      <section role="alert">
        <h1 className="display">{copy.title}</h1>
        <p>{copy.body}</p>
        <div className="status-page-actions">
          <button type="button" className="button-primary" onClick={() => retry()}>{copy.retry}</button>
          <Link href="/dashboard" className="button-secondary">{copy.home}</Link>
        </div>
      </section>
    </main>
  );
}
