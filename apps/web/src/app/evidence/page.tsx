import { redirect } from "next/navigation";

/** My Experience used to live here. The old link keeps working. */
export default function EvidenceRedirect() {
  redirect("/experience");
}
