import { Suspense } from "react";
import { Loader } from "@/components/loader";
import { loading } from "@/lib/copy";
import { AuthForm } from "@/components/auth-form";

export default function SignupPage() {
  return <Suspense fallback={<main className="shell"><Loader page label={loading.signUp.label} note={loading.signUp.note} /></main>}><AuthForm mode="signup" /></Suspense>;
}

