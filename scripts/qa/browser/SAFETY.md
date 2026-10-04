# Browser QA safety status: BLOCKED

`run.mjs` deliberately exits nonzero before filesystem artifacts, listeners, Next, or browser activity. Direct `runCriticalPath()` also refuses execution. There is no environment variable, CLI flag, or caller assertion that enables isolation. This is not a working hermetic browser suite or a hermetic PASS.

The unsafe ordinary `apps/web/.next` build/start/reuse path was removed, including inherited child environment, real Next/dotenv discovery, weak URL substring check, and unbound build marker. Existing earlier build/artifacts are not trusted, reused, cleaned, or altered by this repair.

## Foundations repaired
- Strict CLI options; unknown/empty/duplicate `--only` cannot select zero viewports.
- Summary requires positive executed viewport/step counts; skipped/failing steps and any known typing defect/workaround fail the gate.
- Browser defense-in-depth permits exact QA HTTP origins only, denies every websocket, blocks service workers, records denied origins without query strings, and fails results for denied requests. This is unit-tested, NOT browser-exercised and NOT an SSR/build rail.
- Mock Host and optional Origin must match explicit policy; CORS preflight headers are fixed. Reset/state require a random per-run control token, provided in memory and not logged. Both listeners check policy before dispatch. Partial bind failure closes both servers.
- Fixtures and their external contract ownership are unchanged.

## Required before execution can be restored
1. Implement and independently approve an OS/container-level build + Next SSR + browser egress boundary, covering native/subprocess networking and unrelated loopback services. Prove negative-denial cases; mere flags or callback assertions are not evidence.
2. Implement fresh QA-only scratch staging, excluding all dotenv/secret files, no source/config symlinks back to the product tree, and generated QA Next config that cannot discover/load real dotenv. Never overwrite product Next config or mutate/reuse ordinary `.next`.
3. Use a fixed minimal environment allow-list (no `process.env` spread or arbitrary `NEXT_PUBLIC_*`, `NODE_OPTIONS`, proxy/provider credentials). Spawn Node via absolute `process.execPath`; sandbox HOME/temp/cache paths and any runtime browser environment.
4. Bind any future build marker to exact BUILD_ID plus content hashes and isolated tree provenance. Reject prior weak markers/builds.
5. Reconcile explicit web/auth/API ports and mock allowedOrigins within that isolated boundary, then exercise actual browser redirects/workers/websockets and mock CORS/token/cleanup integration under approved runtime conditions.

## Allowed no-network verification
From repo root:
```
"C:/Program Files/nodejs/node.exe" --test scripts/qa/browser/tests/safety.test.mjs scripts/qa/browser/tests/mock-safety.test.mjs scripts/qa/browser/tests/network.test.mjs
```
Tests use pure policies, fake browser/server objects, static wiring checks, and blocked CLI/direct-entry smoke checks only. They do not build Next, launch browsers, bind listeners, install packages, or contact hosted services.
