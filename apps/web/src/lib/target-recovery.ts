import type { TargetCreate, TargetView } from "@/lib/api-targets";

export function activeTargetsForRole(targets: TargetView[], roleProfileId: string): TargetView[] {
  return targets.filter((item) => item.role_profile_id === roleProfileId && item.status === "ACTIVE");
}

/** A requested target is never silently replaced by a different company; only one unambiguous active target auto-selects. */
export function selectTargetForRole(targets: TargetView[], roleProfileId: string, requestedTargetId?: string): TargetView | null {
  const active = activeTargetsForRole(targets, roleProfileId);
  if (requestedTargetId) return active.find((item) => item.id === requestedTargetId) ?? null;
  return active.length === 1 ? active[0] : null;
}

export function createRequestSequence() {
  let latest = 0;
  return {
    next: () => ++latest,
    isCurrent: (request: number) => request === latest,
  };
}

export type RecoveryApi = {
  create: (body: TargetCreate) => Promise<{ target: TargetView }>;
  list: () => Promise<{ availability: string; targets: TargetView[] }>;
  blueprint: (id: string) => Promise<unknown>;
};
export type RecoveryResult = { kind: "READY"; target: TargetView } | { kind: "FAILED" };

export async function recoverTarget(body: TargetCreate, api: RecoveryApi): Promise<RecoveryResult> {
  try {
    const created = await api.create(body);
    await api.blueprint(created.target.id);
    return { kind: "READY", target: created.target };
  } catch {
    return recoverExisting(body, api);
  }
}

async function recoverExisting(body: TargetCreate, api: RecoveryApi): Promise<RecoveryResult> {
  try {
    const list = await api.list();
    if (list.availability !== "AVAILABLE") return { kind: "FAILED" };
    const target = list.targets.find((item) => item.status === "ACTIVE"
      && item.role_profile_id === body.role_profile_id
      && item.company_label.trim().toLocaleLowerCase() === body.company.trim().toLocaleLowerCase()
      && item.role_family_key === body.role_family
      && item.level_key === body.level
      && (item.geography_key ?? null) === (body.geography ?? null));
    if (!target) return { kind: "FAILED" };
    await api.blueprint(target.id);
    return { kind: "READY", target };
  } catch {
    return { kind: "FAILED" };
  }
}
