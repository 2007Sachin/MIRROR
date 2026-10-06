/**
 * Interview targets (Loop 2): company, country and level for one role, the pinned research
 * blueprint and Mirror's practice rounds. The backend owns every rule (`routes_targets.py`);
 * this module only types and calls it. Target data is optional: when the service is switched
 * off or its tables are missing the reads say so (`availability`), and callers stay quiet.
 */
import { ApiError, request } from "@/lib/api";
import { failureKind } from "@/lib/copy-targets";

export type TargetAvailability = "AVAILABLE" | "UNAVAILABLE" | "DISABLED";
export type LevelKey = "sde_i" | "sde_ii" | "sde_iii" | "university" | "not_sure";

export type TargetView = {
  id: string;
  role_profile_id: string;
  company_label: string;
  company_key: string | null;
  role_family_key: string;
  level_key: string | null;
  geography_key: string | null;
  geography_label: string | null;
  interview_date: string | null;
  status: string;
  archived_at: string | null;
  created_at: string;
};

export type SourceRef = { publisher: string; url: string; retrieved_at: string; published_at: string | null };

export type ClaimView = {
  key: string;
  version: number;
  statement: string;
  provenance_class: string;
  class_label_key: string;
  scope: Record<string, string>;
  scope_label_key: string;
  confidence_band: string;
  dating: string;
  retrieved_at: string;
  published_at: string | null;
  limits: string[];
  sources: SourceRef[];
  conflict_set: string | null;
};

export type ConflictView = { key: string; note: string; claims: ClaimView[] };
export type UnknownView = { key: string; reason: string; note: string };
export type RoundSummary = {
  key: string;
  ordinal: number;
  label_key: string;
  basis: "PUBLISHED_GUIDANCE" | "MIRROR_SUGGESTED";
  competency_keys: string[];
};

export type BlueprintView = {
  availability: TargetAvailability;
  target: TargetView | null;
  blueprint: { version: number; catalog_version: number; match_state: string; latest_version: number; refresh_available: boolean } | null;
  content_state: "SERVED" | "PIN_MISMATCH" | "CATALOG_UNAVAILABLE" | null;
  match_state: string | null;
  research_label_key: string | null;
  claims: ClaimView[];
  conflicts: ConflictView[];
  unknowns: UnknownView[];
  rounds: RoundSummary[];
};

export type PromptView = { position: number; text: string; competency_key: string; rationale_code: string; provenance_class: string };

export type RoundDetail = {
  availability: TargetAvailability;
  target: TargetView | null;
  round: RoundSummary | null;
  match_state: string | null;
  research_label_key: string | null;
  content_state: string | null;
  claims: ClaimView[];
  conflicts: ConflictView[];
  unknowns: UnknownView[];
  priorities: { rank: number; competency_key: string; reason_codes: string[]; suggested_mode: string }[];
  pack: { state: "FULL" | "SHORT_PACK" | string; minimum: number; label_key: string; prompts: PromptView[] } | null;
  practice: { count: number; sessions: { session_id: string; created_at: string }[] } | null;
};

export type PracticeStarted = {
  session: { id: string };
  link: { session_id: string; candidate_target_id: string; round_key: string | null };
  prompts: { position: number; rationale_code: string }[];
};

export type TargetCreate = {
  role_profile_id: string;
  company: string;
  level: LevelKey;
  geography?: string | null;
  geography_label?: string | null;
};

const JSON_HEADERS = { "Content-Type": "application/json" };

export function listTargets() {
  return request<{ availability: TargetAvailability; targets: TargetView[] }>("/api/v1/targets");
}

export function getTarget(targetId: string) {
  return request<{ availability: TargetAvailability; target: TargetView | null }>(`/api/v1/targets/${encodeURIComponent(targetId)}`);
}

export function createTarget(body: TargetCreate) {
  return request<{ target: TargetView }>("/api/v1/targets", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) });
}

export function getBlueprint(targetId: string) {
  return request<BlueprintView>(`/api/v1/targets/${encodeURIComponent(targetId)}/blueprint`);
}

export function getRound(targetId: string, roundKey: string) {
  return request<RoundDetail>(`/api/v1/targets/${encodeURIComponent(targetId)}/rounds/${encodeURIComponent(roundKey)}`);
}

export function startRoundPractice(targetId: string, roundKey: string, mode: "QUICK_DRILL" | "FOCUSED_PRACTICE", idempotencyKey: string) {
  return request<PracticeStarted>(
    `/api/v1/targets/${encodeURIComponent(targetId)}/rounds/${encodeURIComponent(roundKey)}/practice`,
    { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ mode, idempotency_key: idempotencyKey }) },
  );
}

/** The newest active target for one role, if targets are available at all. */
export type RoleTarget =
  | { kind: "UNAVAILABLE" }
  | { kind: "NONE" }
  | { kind: "TARGET"; target: TargetView };

export async function targetForRole(roleProfileId: string): Promise<RoleTarget> {
  try {
    const list = await listTargets();
    if (list.availability !== "AVAILABLE") return { kind: "UNAVAILABLE" };
    const target = list.targets.find((item) => item.role_profile_id === roleProfileId && item.status === "ACTIVE");
    return target ? { kind: "TARGET", target } : { kind: "NONE" };
  } catch (reason) {
    if (reason instanceof ApiError && failureKind(reason.status) === "UNAVAILABLE") return { kind: "UNAVAILABLE" };
    throw reason;
  }
}

/** Target availability for forms: anything but a clear AVAILABLE hides the optional target fields. */
export async function targetsAvailable(): Promise<boolean> {
  try {
    return (await listTargets()).availability === "AVAILABLE";
  } catch {
    return false;
  }
}
