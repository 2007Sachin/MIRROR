"use client";

import "@/styles/onboarding.css";
import "@/styles/onboarding-plan.css";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { PlanReadyStep } from "@/components/onboarding/plan-ready-step";
import { RoleStep, type RoleSetup } from "@/components/onboarding/role-step";
import { useReport } from "@/components/onboarding/shared";
import { PageShell } from "@/components/workspace/page-shell";
import { setActiveRole } from "@/lib/api-active-role";
import { onboardingCopy } from "@/lib/copy-onboarding";

const t = onboardingCopy;

/** Adding a role: the role step, then that role's plan. It becomes the active role; nothing else changes. */
export function NewRoleFlow() {
  const router = useRouter();
  const { error, report } = useReport();
  const [setup, setSetup] = useState<RoleSetup | null>(null);

  async function roleReady(next: RoleSetup) {
    try {
      await setActiveRole(next.role.id);
    } catch (reason) {
      return report(t.errors.save, reason);
    }
    setSetup(next);
  }

  async function exit(href: string) {
    router.push(href);
  }

  return (
    <PageShell>
      <div className="op-flow op-flow--embedded">
        {setup ? (
          <PlanReadyStep
            eyebrow={t.newRole.eyebrow}
            note={t.newRole.activeNote}
            roleProfileId={setup.role.id}
            roleName={setup.role.target_role}
            report={report}
            onExit={exit}
          />
        ) : (
          <RoleStep eyebrow={t.newRole.eyebrow} withCompany={false} report={report} onReady={roleReady} />
        )}
        {error && <p role="alert" className="ob-error">{error}</p>}
      </div>
    </PageShell>
  );
}
