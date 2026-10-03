/**
 * My plan: each role need once, with what you already have and the next step. The backend
 * builds it (`GET /api/v1/plan`); this module only fetches it and records your link choices.
 */
import { request } from "@/lib/api";

export type PlanState = "READY" | "NEEDS_REVIEW" | "PREPARING" | "UNAVAILABLE" | "NO_ROLE";
export type PlanStatus = "STRONG" | "GOOD" | "BUILD";
export type PlanAction = "PRACTICE" | "STORY" | "ADD_EXAMPLE";
export type LinkReason = "TOOL" | "OUTCOME" | "DECISION" | "CAPABILITY" | "CONFIRMED";

export type PlanLink = {
  kind: "EXPERIENCE" | "STORY";
  title: string;
  reason: LinkReason | null;
  evidence_item_id: string | null;
  story_id: string | null;
};

export type PlanArea = {
  key: string;
  title: string;
  theme: string;
  from_job_description: boolean;
  why: string | null;
  status: PlanStatus;
  have: PlanLink[];
  suggested: PlanLink[];
  strengthen: string;
  primary_action: PlanAction;
};

export type Plan = {
  role: { role_profile_id: string; target_role: string } | null;
  state: PlanState;
  areas: PlanArea[];
  recommended_area_key: string | null;
};

export function getPlan(roleProfileId?: string | null) {
  const query = roleProfileId ? `?role_profile_id=${encodeURIComponent(roleProfileId)}` : "";
  return request<Plan>(`/api/v1/plan${query}`);
}

/** Confirm (true) or dismiss (false) one example or story for one need. Returns the rebuilt plan. */
export function choosePlanLink(roleProfileId: string, areaKey: string, link: PlanLink, confirmed: boolean) {
  const target = link.evidence_item_id ? { evidence_item_id: link.evidence_item_id } : { story_id: link.story_id };
  return request<Plan>(
    `/api/v1/plan/${encodeURIComponent(roleProfileId)}/areas/${encodeURIComponent(areaKey)}/link`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...target, confirmed }),
    },
  );
}
