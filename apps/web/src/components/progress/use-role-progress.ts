"use client";

import { usePageData } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type RoleProgress } from "@/lib/api";
import { progress as t } from "@/lib/copy";

const TTL_MS = 60_000;
const recent = new Map<string, { at: number; value: Promise<RoleProgress | null> }>();

/**
 * One role's progress. Moving between its pages reuses the last read for a minute, so
 * the drill-down does not wait on the same data again. A role that is not this
 * person's (or does not exist) comes back as null, never as someone else's data.
 */
function load(roleProfileId: string) {
  const hit = recent.get(roleProfileId);
  if (hit && Date.now() - hit.at < TTL_MS) return hit.value;
  const value = mirrorApi.roleProgress(roleProfileId).catch((reason: unknown) => {
    if (reason instanceof ApiError && reason.status === 404) return null;
    recent.delete(roleProfileId);
    throw reason;
  });
  recent.set(roleProfileId, { at: Date.now(), value });
  return value;
}

export function useRoleProgress(roleProfileId: string) {
  return usePageData(() => load(roleProfileId), t.errors.load, [roleProfileId]);
}
