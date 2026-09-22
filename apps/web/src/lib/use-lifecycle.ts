"use client";

import { useEffect, useRef } from "react";

import { ApiError, mirrorApi } from "@/lib/api";

const HEARTBEAT_MS = 15_000;

/** A stable id for this browser tab (sessionStorage is per tab). */
function tabLeaseId(): string {
  try {
    const existing = window.sessionStorage.getItem("mirror.lease");
    if (existing) return existing;
    const fresh = crypto.randomUUID();
    window.sessionStorage.setItem("mirror.lease", fresh);
    return fresh;
  } catch {
    return crypto.randomUUID();
  }
}

/**
 * Tells the server this tab is live while the room is joined. If the conversation is open in
 * another tab, `onOpenElsewhere` fires once; after repeated network failures `onConnectionLost` fires once.
 */
export function useLifecycle(
  sessionId: string,
  active: boolean,
  handlers: { onOpenElsewhere: () => void; onConnectionLost: () => void },
) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!active) return;
    const lease = tabLeaseId();
    let failures = 0;
    let stopped = false;
    const beat = async () => {
      if (stopped) return;
      try {
        await mirrorApi.heartbeat(sessionId, lease);
        failures = 0;
      } catch (caught) {
        if (caught instanceof ApiError && caught.code === "SESSION_OPEN_ELSEWHERE") {
          stopped = true;
          handlersRef.current.onOpenElsewhere();
        } else if (!(caught instanceof ApiError)) {
          failures += 1;
          if (failures === 3) handlersRef.current.onConnectionLost();
        }
      }
    };
    void beat();
    const timer = window.setInterval(() => void beat(), HEARTBEAT_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [sessionId, active]);
}
