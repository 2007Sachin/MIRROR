"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { ACTIVE_ROLE_KEY, getActiveRole, setActiveRole, type ActiveRoleState } from "@/lib/api-active-role";
import { shellCopy } from "@/lib/copy-shell";
import { peekCached, setCached } from "@/lib/session-cache";

const copy = shellCopy.roleSwitcher;

/**
 * "Preparing for: <role>" in the top bar. A native select keeps it keyboard and
 * screen-reader friendly. If the roles cannot be read, or there are none, it renders
 * nothing: the shell must never break because of it.
 */
export function RoleSwitcher() {
  const router = useRouter();
  const id = useId();
  const [state, setState] = useState<ActiveRoleState | null>(() => peekCached<ActiveRoleState>(ACTIVE_ROLE_KEY) ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let live = true;
    getActiveRole()
      .then((next) => {
        if (live && Array.isArray(next?.roles)) setState(next);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  if (!state || state.roles.length === 0) return null;

  async function choose(roleProfileId: string) {
    const role = state?.roles.find((item) => item.role_profile_id === roleProfileId);
    if (!state || !role || role.role_profile_id === state.role?.role_profile_id) return;
    setBusy(true);
    setError(false);
    try {
      await setActiveRole(role.role_profile_id);
      const next = { ...state, role };
      setCached(ACTIVE_ROLE_KEY, next);
      setState(next);
      router.refresh();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ws-role-switcher">
      <label htmlFor={id}>{copy.label}</label>
      <select
        id={id}
        value={state.role?.role_profile_id ?? ""}
        disabled={busy}
        aria-busy={busy}
        onChange={(event) => void choose(event.target.value)}
      >
        {state.role ? null : <option value="" disabled>{copy.choose}</option>}
        {state.roles.map((role) => (
          <option key={role.role_profile_id} value={role.role_profile_id}>{role.target_role}</option>
        ))}
      </select>
      <Link href="/roles/new" className="ws-role-add">{copy.addRole}</Link>
      {error ? <p className="ws-role-error" role="status">{copy.switchFailed}</p> : null}
    </div>
  );
}
