import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";

export default function SignupPage() {
  return <Suspense fallback={<main className="shell py-20 text-[var(--silver)]">Loading sign up…</main>}><AuthForm mode="signup" /></Suspense>;
}

