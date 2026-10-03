"use client";

import { useEffect, useState } from "react";

import { mirrorApi, type Session } from "@/lib/api";
import { practiceFocus } from "@/lib/copy";
import { focusFor, modeCopy } from "@/lib/practice-view";

/** On the pre-interview brief, keep the displayed duration tied to the actual session mode. */
export function PracticeBriefNote({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    let active = true;
    void mirrorApi.session(sessionId).then((next) => active && setSession(next)).catch(() => undefined);
    return () => {
      active = false;
    };
  }, [sessionId]);

  if (!session?.practice_mode) return null;
  const area = session.practice_theme ?? focusFor(session.practice_focus)?.title;
  return (
    <>
      {session.practice_mode !== "FULL_INTERVIEW" ? (
        <div className="sb-focus">
          <p>{practiceFocus.reminderLabel}</p>
          <strong>{area ? `${modeCopy(session.practice_mode).title} · ${area}` : modeCopy(session.practice_mode).title}</strong>
          <span>{modeCopy(session.practice_mode).length}</span>
        </div>
      ) : null}
      <p className="mt-6 text-xs leading-5 text-[var(--silver)]">
        {modeCopy(session.practice_mode).length}. There are no ratings or tips during the conversation; your reflection comes afterward.
      </p>
    </>
  );
}
