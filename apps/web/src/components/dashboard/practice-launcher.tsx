"use client";

import { ArrowRight, X } from "@phosphor-icons/react";
import Link from "next/link";
import { useId, useRef, useState } from "react";

import type { PracticeOption } from "@/lib/dashboard-view";
import { home } from "@/lib/copy";

export function PracticeLauncher({
  options,
  label = home.startPractice,
  preferredRole,
  onQuickStart,
  quiet = false,
}: {
  options: PracticeOption[];
  label?: string;
  preferredRole?: string;
  onQuickStart: (role: string) => Promise<void>;
  quiet?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [busyRole, setBusyRole] = useState<string | null>(null);
  const [error, setError] = useState("");
  const preferred = preferredRole
    ? options.find((option) => option.role.toLocaleLowerCase() === preferredRole.toLocaleLowerCase())
    : null;
  const direct = preferred ?? (options.length === 1 ? options[0] : null);
  const triggerClass = quiet ? "dh-text-action" : "dh-primary-action";

  async function quickStart(role: string) {
    setBusyRole(role);
    setError("");
    try {
      await onQuickStart(role);
      dialog.current?.close();
    } catch {
      setError(home.practicePicker.failed);
    } finally {
      setBusyRole(null);
    }
  }

  if (direct?.href) {
    return (
      <Link className={triggerClass} href={direct.href}>
        {label} <ArrowRight size={17} aria-hidden="true" />
      </Link>
    );
  }

  if (direct?.quickStart) {
    return (
      <span className="dh-launcher-inline">
        <button className={triggerClass} type="button" disabled={busyRole !== null} onClick={() => void quickStart(direct.role)}>
          {busyRole ? home.practicePicker.preparing : label} {!busyRole ? <ArrowRight size={17} aria-hidden="true" /> : null}
        </button>
        {error ? <span className="dh-inline-error" role="alert">{error}</span> : null}
      </span>
    );
  }

  if (options.length === 0) {
    return (
      <Link className={triggerClass} href="/sessions/new">
        {label} <ArrowRight size={17} aria-hidden="true" />
      </Link>
    );
  }

  return (
    <>
      <button className={triggerClass} type="button" onClick={() => dialog.current?.showModal()}>
        {label} <ArrowRight size={17} aria-hidden="true" />
      </button>
      <dialog ref={dialog} className="dh-role-dialog" aria-labelledby={titleId}>
        <div className="dh-role-dialog-panel">
          <header>
            <div>
              <p className="dh-section-label">{home.startPractice}</p>
              <h2 id={titleId}>{home.practicePicker.title}</h2>
              <p>{home.practicePicker.body}</p>
            </div>
            <button type="button" className="dh-dialog-close" onClick={() => dialog.current?.close()} aria-label={home.practicePicker.close}>
              <X size={19} aria-hidden="true" />
            </button>
          </header>

          <div className="dh-role-options">
            {options.map((option) => option.href ? (
              <Link key={option.role} href={option.href} onClick={() => dialog.current?.close()}>
                <span><strong>{option.role}</strong><small>{option.description}</small></span>
                <ArrowRight size={17} aria-hidden="true" />
              </Link>
            ) : (
              <button key={option.role} type="button" disabled={busyRole !== null} onClick={() => void quickStart(option.role)}>
                <span><strong>{option.role}</strong><small>{option.description}</small></span>
                <ArrowRight size={17} aria-hidden="true" />
              </button>
            ))}
            <Link href="/sessions/new" onClick={() => dialog.current?.close()}>
              <span><strong>{home.practicePicker.another}</strong><small>{home.continuePreparing.another}</small></span>
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </div>
          {error ? <p className="dh-dialog-error" role="alert">{error}</p> : null}
        </div>
      </dialog>
    </>
  );
}
