"use client";

import "@/styles/dashboard.css";

import { ArrowLeft, ArrowRight, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Loader } from "@/components/loader";
import { AppShell } from "@/components/workspace/app-shell";
import { ApiError, mirrorApi, type Profile } from "@/lib/api";
import { loading } from "@/lib/copy";

/**
 * The profile behind every authenticated page. A profile that cannot be loaded is
 * never fatal: the page still renders, only the name in the corner is missing.
 */
export function useProfile() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  useEffect(() => {
    let active = true;
    void mirrorApi
      .me()
      .then((next) => {
        if (active) setProfile(next);
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiError && reason.status === 401) router.replace("/login?reason=session_expired");
      });
    return () => {
      active = false;
    };
  }, [router]);
  return profile;
}

type LoadState = "loading" | "ready" | "error";

/**
 * Loads one page's data once, sends an expired session back to sign-in, and keeps
 * the three states every page needs in one place instead of in each component.
 */
export function usePageData<T>(load: () => Promise<T>, failureMessage: string, deps: unknown[] = []) {
  const router = useRouter();
  const mounted = useRef(true);
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");

  const run = useCallback(async () => {
    setError("");
    try {
      const next = await load();
      if (!mounted.current) return;
      setData(next);
      setState("ready");
    } catch (reason) {
      if (!mounted.current) return;
      if (reason instanceof ApiError && reason.status === 401) {
        router.replace("/login?reason=session_expired");
        return;
      }
      setState("error");
      setError(failureMessage);
    }
    // `load` is redeclared on every render by most callers, so it is deliberately
    // not a dependency. `deps` names the values that should load the page again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [failureMessage, router, ...deps]);

  useEffect(() => {
    mounted.current = true;
    void run();
    return () => {
      mounted.current = false;
    };
  }, [run]);

  return { state, data, error, reload: run, setData } as const;
}

export function PageShell({ children }: { children: ReactNode }) {
  const profile = useProfile();
  return (
    <AppShell profile={profile}>
      <div className="dh">{children}</div>
    </AppShell>
  );
}

export function PageHeader({
  eyebrow,
  title,
  intro,
  action,
  back,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  action?: ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <header className="dh-page-header">
      {back ? (
        <Link className="dh-back-link" href={back.href}>
          <ArrowLeft size={15} aria-hidden="true" /> {back.label}
        </Link>
      ) : null}
      <div className="dh-page-header-row">
        <div>
          <p className="dh-section-label">{eyebrow}</p>
          <h1 className="dh-title display">{title}</h1>
          {intro ? <p className="dh-page-intro">{intro}</p> : null}
        </div>
        {action}
      </div>
    </header>
  );
}

export function PageLoading({ label, note }: { label?: string; note?: string }) {
  return <Loader label={label ?? loading.space.label} note={note ?? loading.space.note} />;
}

export function PageAlert({ message, onRetry, retryLabel }: { message: string; onRetry?: () => void; retryLabel?: string }) {
  return (
    <div className="dh-alert" role="alert">
      <span>
        <WarningCircle size={17} aria-hidden="true" /> {message}
      </span>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          {retryLabel ?? "Try again"}
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
  children,
}: {
  title: string;
  body: string;
  action?: { href: string; label: string };
  /** For an action that opens something here rather than going somewhere else. */
  children?: ReactNode;
}) {
  return (
    <section className="dh-empty">
      <h2>{title}</h2>
      <p>{body}</p>
      {action ? (
        <Link className="dh-primary-action" href={action.href}>
          {action.label} <ArrowRight size={16} aria-hidden="true" />
        </Link>
      ) : null}
      {children}
    </section>
  );
}

export function Section({
  label,
  title,
  body,
  action,
  children,
  id,
}: {
  label?: string;
  title: string;
  body?: string;
  action?: ReactNode;
  children: ReactNode;
  id: string;
}) {
  return (
    <section className="dh-section" aria-labelledby={`${id}-title`}>
      <div className="dh-section-heading">
        <div>
          {label ? <p className="dh-section-label">{label}</p> : null}
          <h2 id={`${id}-title`} className="display">
            {title}
          </h2>
          {body ? <p className="dh-section-body">{body}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
