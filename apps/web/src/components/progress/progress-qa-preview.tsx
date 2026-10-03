"use client";

import "@/styles/dashboard.css";
import "@/styles/progress.css";

import { AnswerView } from "@/components/progress/answer-detail";
import { DimensionAnswersView } from "@/components/progress/dimension-answers";
import { DimensionView } from "@/components/progress/dimension-detail";
import { ProgressHubView } from "@/components/progress/progress-hub";
import { RoleProgressView } from "@/components/progress/role-progress";
import { AppShell } from "@/components/workspace/app-shell";
import { answerFixture, roleProgressFixture, tilesFixture, type ProgressQaScenario } from "@/lib/progress-qa-fixtures";
import { isRoleTab } from "@/lib/progress-view";

export type ProgressQaView = "hub" | "role" | "dimension" | "answers" | "answer";

/** Local-only preview of the Progress pages with synthetic data. See docs/architecture/HOME_QA.md. */
export function ProgressQaPreview({
  view,
  tab,
  dimension,
  scenario,
}: {
  view: ProgressQaView;
  tab: string | undefined;
  dimension: string;
  scenario: ProgressQaScenario;
}) {
  const data = roleProgressFixture(scenario);
  return (
    <AppShell profile={{ id: "qa-user", full_name: "Jordan Lee", email: "jordan@example.test" }}>
      <div className="dh">
        <p className="sr-only" role="status">QA preview with synthetic data: {view}, {scenario}</p>
        {view === "hub" ? <ProgressHubView roles={scenario === "none" ? [] : tilesFixture()} /> : null}
        {view === "role" ? <RoleProgressView data={data} tab={isRoleTab(tab) ? tab : "overview"} /> : null}
        {view === "dimension" ? <DimensionView data={data} dimensionKey={dimension} /> : null}
        {view === "answers" ? <DimensionAnswersView data={data} dimensionKey={dimension} /> : null}
        {view === "answer" ? <AnswerView data={answerFixture()} dimension={dimension === "none" ? null : dimension} onSaved={() => undefined} /> : null}
      </div>
    </AppShell>
  );
}
