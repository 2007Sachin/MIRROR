import { notFound } from "next/navigation";

import { ProgressQaPreview, type ProgressQaView } from "@/components/progress/progress-qa-preview";
import type { ProgressQaScenario } from "@/lib/progress-qa-fixtures";

export const dynamic = "force-dynamic";

const VIEWS: ProgressQaView[] = ["hub", "role", "dimension", "answers", "answer"];
const SCENARIOS: ProgressQaScenario[] = ["comparable", "baseline", "none"];

/** Local-only visual QA harness for Progress. See docs/architecture/HOME_QA.md. */
export default async function ProgressQaPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string; tab?: string; dimension?: string; scenario?: string }>;
}) {
  if (process.env.NODE_ENV === "production" || process.env.MIRROR_HOME_QA !== "1") notFound();
  const { view, tab, dimension, scenario } = await searchParams;
  return (
    <ProgressQaPreview
      view={VIEWS.find((item) => item === view) ?? "hub"}
      tab={tab}
      dimension={dimension ?? "depth"}
      scenario={SCENARIOS.find((item) => item === scenario) ?? "comparable"}
    />
  );
}
