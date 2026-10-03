import { notFound } from "next/navigation";

import { interviewsQaFixtures } from "@/lib/interviews-qa-fixtures";

export const dynamic = "force-dynamic";

/** The fixture JSON the Playwright script stubs the API with. Same gate as the page. */
export function GET() {
  if (process.env.NODE_ENV === "production" || process.env.MIRROR_HOME_QA !== "1") notFound();
  return Response.json(interviewsQaFixtures);
}
