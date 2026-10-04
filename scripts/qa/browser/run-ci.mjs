// CI browser critical path. Runs ONLY on an approved ephemeral GitHub-hosted runner (lib/isolation.mjs).
// Usage (after `next build` with loopback NEXT_PUBLIC_* values): node scripts/qa/browser/run-ci.mjs
// Starts the fake Supabase Auth + fake Mirror API, `next start` on loopback, drives system Chrome through
// the desktop and mobile critical path, writes artifacts/summary.json and screenshots, exits nonzero on any failure.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { parseArgs } from './lib/safety.mjs';
import { requireEphemeralRunner } from './lib/isolation.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const AUTH_PORT = 54399, API_PORT = 8099, WEB_PORT = 3099;
const WEB = `http://127.0.0.1:${WEB_PORT}`;
let web;
let mock;

async function waitFor(url, ms) {
  const deadline = Date.now() + ms;
  for (;;) {
    try { const res = await fetch(url, { redirect: 'manual' }); if (res.status < 500) return; } catch { /* not up yet */ }
    if (Date.now() > deadline) throw new Error(`web server did not become ready: ${WEB}`);
    await new Promise((r) => setTimeout(r, 500));
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  requireEphemeralRunner();
  // Imports that start nothing are deferred until the environment is approved.
  const { startMock } = await import('./mock/server.mjs');
  const { runCriticalPath, VIEWPORTS } = await import('./tests/critical-path.mjs');
  const password = crypto.randomBytes(18).toString('base64url'); // in memory only, never logged
  mock = await startMock({
    authPort: AUTH_PORT, apiPort: API_PORT, password,
    supabaseUrl: `http://127.0.0.1:${AUTH_PORT}`, apiUrl: `http://127.0.0.1:${API_PORT}`, allowedOrigins: [WEB],
  });
  const nextBin = path.join(root, 'node_modules', 'next', 'dist', 'bin', 'next');
  const childEnv = {
    PATH: process.env.PATH, HOME: process.env.HOME, NODE_ENV: 'production', NEXT_TELEMETRY_DISABLED: '1',
    NEXT_PUBLIC_SUPABASE_URL: `http://127.0.0.1:${AUTH_PORT}`, NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}`,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: 'qa-sentinel-anon-key',
  };
  web = spawn(process.execPath, [nextBin, 'start', '-H', '127.0.0.1', '-p', String(WEB_PORT)], { cwd: path.join(root, 'apps', 'web'), env: childEnv, stdio: ['ignore', 'inherit', 'inherit'] });
  await waitFor(`${WEB}/login`, 90_000);
  const outDir = path.join(here, 'artifacts');
  fs.mkdirSync(outDir, { recursive: true });
  const viewports = options.only ? VIEWPORTS.filter((v) => v.name === options.only) : VIEWPORTS;
  const summary = await runCriticalPath({ baseUrl: WEB, mock, password, outDir, viewports });
  fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2));
  console.log(`browser critical path: ok=${summary.ok} viewports=${summary.executedViewports} steps=${summary.executedSteps}`);
  return summary.ok;
}

let ok = false;
try { ok = await main(); } catch (error) { console.error(`run-ci.mjs: ${error.message}`); }
finally {
  web?.kill();
  await mock?.close().catch(() => {});
}
process.exit(ok ? 0 : 1);
