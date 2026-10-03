import { redirect } from "next/navigation";

// The progress hub now lives inside Reflect; /progress/[roleProfileId]/* pages are unchanged.
export default function Progress() {
  redirect("/reflect");
}
