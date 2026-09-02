import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";

export default function LoginPage() {
  return <Suspense fallback={<main className="shell py-20 text-[var(--silver)]">Loading sign in…</main>}><AuthForm mode="login" /></Suspense>;
}

