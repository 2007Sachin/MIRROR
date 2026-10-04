// Standalone mock for manual poking:  MIRROR_QA_PASSWORD=<something> node start-mock.mjs
// The password comes from YOUR environment (never a file) and is never printed.
// run.mjs does not use this entry: it starts the mock in-process with a random per-run password.
import { startMock } from "./mock/server.mjs";

const password = process.env.MIRROR_QA_PASSWORD;
if (!password) {
  console.error("start-mock: set MIRROR_QA_PASSWORD in your environment (a throwaway value; it is never printed).");
  process.exit(2);
}
const mock = await startMock({
  password,
  authPort: Number(process.env.MIRROR_QA_AUTH_PORT ?? 0),
  apiPort: Number(process.env.MIRROR_QA_API_PORT ?? 0),
});
console.log(`qa-mock: fake Supabase Auth on ${mock.authUrl}, fake Mirror API on ${mock.apiUrl}, user ${mock.email}`);
console.log("qa-mock: Ctrl+C to stop.");
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => void mock.close().then(() => process.exit(0)));
