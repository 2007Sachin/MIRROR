import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";
import path from "node:path";

const repositoryRoot = path.resolve(__dirname, "../..");

// The web workspace is started from apps/web, while local configuration lives
// at the repository root for both the web app and FastAPI service.
loadEnvConfig(repositoryRoot);

const clientEnvironment = Object.fromEntries(
  Object.entries(process.env).filter(([name]) => name.startsWith("NEXT_PUBLIC_")),
);

const nextConfig: NextConfig = {
  poweredByHeader: false,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Next compiles browser variables before its workspace-level .env discovery.
  // Explicitly forward the root project's public variables; secrets stay server-only.
  env: clientEnvironment,
  outputFileTracingRoot: repositoryRoot,
};

export default nextConfig;

