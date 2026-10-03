"use client";

import { useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { abandonPractice } from "@/lib/api-practice";
import { discardPractice as t } from "@/lib/copy-practice";

/**
 * "Discard this practice": separate from Continue, named plainly, and always asks first.
 * Confirming calls the abandon endpoint; the practice gets no review and leaves the lists.
 */
export function DiscardPractice({ sessionId, onDiscarded }: { sessionId: string; onDiscarded: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const group = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  // Focus follows the person: into the question when it opens, back to the button when it closes.
  function open() {
    setMessage("");
    setConfirming(true);
    requestAnimationFrame(() => group.current?.focus());
  }
  function close() {
    setConfirming(false);
    requestAnimationFrame(() => trigger.current?.focus());
  }

  async function discard() {
    setBusy(true);
    setMessage("");
    try {
      await abandonPractice(sessionId);
      onDiscarded();
    } catch (reason) {
      // 409: it finished in the meantime, so reloading moves it into history.
      if (reason instanceof ApiError && reason.status === 409) {
        onDiscarded();
        return;
      }
      setMessage(t.error);
      setBusy(false);
    }
  }

  if (!confirming) {
    return (
      <button ref={trigger} type="button" className="dh-text-action pr-discard" onClick={open}>
        {t.action}
      </button>
    );
  }
  return (
    <div ref={group} tabIndex={-1} className="pr-confirm" role="group" aria-label={t.title}>
      <p>
        <strong>{t.title}</strong> {t.body}
      </p>
      <div className="pr-confirm-actions">
        <button type="button" className="dh-primary-action is-quiet pr-danger" disabled={busy} onClick={() => void discard()}>
          {busy ? t.busy : t.confirm}
        </button>
        <button type="button" className="dh-text-action" disabled={busy} onClick={close}>
          {t.cancel}
        </button>
      </div>
      {message ? <p className="dh-inline-error" role="alert">{message}</p> : null}
    </div>
  );
}
