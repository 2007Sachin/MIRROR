import { Suspense } from "react";
import { Loader } from "@/components/loader";
import { loading } from "@/lib/copy";
import { AuthForm } from "@/components/auth-form";

export default function LoginPage() {
  return <Suspense fallback={<main className="shell"><Loader page label={loading.signIn.label} note={loading.signIn.note} /></main>}><AuthForm mode="login" /></Suspense>;
}

