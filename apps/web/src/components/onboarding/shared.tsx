"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase";

/** Each step's heading. Focus moves here when the step appears so keyboard and screen-reader users land on it. */
export function StepHeading({ title, intro, eyebrow }: { title: string; intro?: string; eyebrow?: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  return (
    <header className="ob-step-header op-heading">
      {eyebrow && <p className="ob-eyebrow">{eyebrow}</p>}
      <h1 ref={heading} tabIndex={-1}>{title}</h1>
      {intro && <p>{intro}</p>}
    </header>
  );
}

/** Reports a problem: an expired sign-in goes back to sign in, anything else shows `message`. Empty message clears. */
export type Report = (message: string, reason?: unknown) => void;

export function useReport() {
  const router = useRouter();
  const [error, setError] = useState("");
  const report = useCallback<Report>((message, reason) => {
    if (reason instanceof ApiError && reason.status === 401) {
      void getSupabaseBrowserClient().auth.signOut().finally(() => router.replace("/login?reason=session_expired"));
      return;
    }
    setError(message);
  }, [router]);
  return { error, report };
}
