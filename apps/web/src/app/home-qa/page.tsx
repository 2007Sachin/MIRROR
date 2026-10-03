import { notFound } from "next/navigation";

import { HomeQaPreview } from "@/components/dashboard/home-qa-preview";
import { homeQaScenario } from "@/lib/home-qa-fixtures";

export const dynamic = "force-dynamic";

/** Local-only visual QA harness. See docs/architecture/HOME_QA.md. */
export default async function HomeQaPage({ searchParams }: { searchParams: Promise<{ scenario?: string }> }) {
  if (process.env.NODE_ENV === "production" || process.env.MIRROR_HOME_QA !== "1") notFound();
  const { scenario } = await searchParams;
  return <HomeQaPreview scenario={homeQaScenario(scenario)} />;
}
