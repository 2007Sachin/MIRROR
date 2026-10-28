"use client";

import "@/styles/dashboard.css";

import { HomeView } from "@/components/dashboard/home-parts";
import { AppShell } from "@/components/workspace/app-shell";
import { HOME_QA_NOW, type HomeQaScenario } from "@/lib/home-qa-fixtures";

const noop = async () => undefined;

/** Local-only preview of Home with a synthetic server decision. See docs/architecture/HOME_QA.md. */
export function HomeQaPreview({ scenario }: { scenario: HomeQaScenario }) {
  return (
    <AppShell profile={{ id: "qa-user", full_name: "Ankit Sunil", email: "ankit@example.test" }}>
      <div className="dh">
        <p className="sr-only" role="status">QA scenario: {scenario.label}</p>
        <HomeView
          data={scenario.data}
          greeting="Good evening"
          firstName="Ankit"
          handlers={{ onSelectRole: () => undefined, onEnd: noop, onRetry: noop }}
          now={HOME_QA_NOW}
        />
      </div>
    </AppShell>
  );
}
