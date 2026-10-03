import { request } from "@/lib/api";
import { cached, invalidateCached } from "@/lib/session-cache";

export const ACTIVE_ROLE_KEY = "active-role";

/** One role the person is preparing for (newest profile per role name). */
export type ActiveRoleOption = { role_profile_id: string; target_role: string };
export type ActiveRoleState = { role: ActiveRoleOption | null; roles: ActiveRoleOption[] };

export function getActiveRole() {
  return cached(ACTIVE_ROLE_KEY, () => request<ActiveRoleState>("/api/v1/active-role"));
}

/** Switching never creates a practice session; it only changes which role is active. */
export function setActiveRole(roleProfileId: string) {
  return request<unknown>("/api/v1/active-role", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role_profile_id: roleProfileId }),
  }).finally(() => invalidateCached(ACTIVE_ROLE_KEY));
}
