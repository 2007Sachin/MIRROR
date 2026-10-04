import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { runCriticalPath } from './critical-path.mjs';

test('CLI exits nonzero for valid build and invalid selection without browser/build', () => {
  for (const [args, expected] of [[['--build', '--only=desktop'], /BLOCKED/], [['--only=unknown'], /Invalid --only/]]) {
    const result = spawnSync(process.execPath, [fileURLToPath(new URL('../run.mjs', import.meta.url)), ...args], { env: {}, encoding: 'utf8', timeout: 5000, windowsHide: true });
    assert.equal(result.status, 1);
    assert.match(result.stderr, expected);
    assert.equal(result.stdout, '');
  }
});

test('direct critical-path calls cannot bypass isolation or select zero viewports', async () => {
  await assert.rejects(runCriticalPath({}), /BLOCKED/);
  await assert.rejects(runCriticalPath({ viewports: [] }), /Invalid viewport/);
});
const safetyUrl = new URL('../lib/safety.mjs', import.meta.url);
const safety = fs.existsSync(safetyUrl) ? await import(safetyUrl.href) : {};

test('execution is BLOCKED even with caller-supplied isolation assertions', () => {
  assert.equal(typeof safety.requireSupportedIsolation, 'function', 'missing fail-closed preflight');
  assert.throws(() => safety.requireSupportedIsolation({ approved: true, boundary: 'trust-me' }), /BLOCKED.*SSR.*build/);
});

test('runner contains no build/start/listener path pending isolation', () => {
  const source = fs.readFileSync(new URL('../run.mjs', import.meta.url), 'utf8');
  assert.match(source, /requireSupportedIsolation\(\)/);
  assert.doesNotMatch(source, /child_process|startMock|\.next|chromium\.launch/);
});

test('invalid or empty --only is rejected rather than selecting no viewports', () => {
  assert.equal(typeof safety.parseArgs, 'function', 'missing strict argument parser');
  for (const args of [['--only=unknown'], ['--only='], ['--only'], ['--unsafe'], ['--only=desktop', '--only=mobile']]) {
    assert.throws(() => safety.parseArgs(args), /Invalid|Unknown|Duplicate/);
  }
  assert.deepEqual(safety.parseArgs(['--build', '--only=desktop']), { build: true, only: 'desktop' });
});

test('empty or skipped execution and known typing workarounds cannot pass', () => {
  assert.equal(typeof safety.resultOk, 'function', 'missing positive execution gate');
  const clean = { steps: [{ ok: true }], knownIssues: [], findings: { pageErrors: [], consoleErrors: [], failedRequests: [], badResponses: [] }, unmockedApiCalls: [] };
  assert.equal(safety.resultOk([]), false);
  assert.equal(safety.resultOk([{ ...clean, steps: [] }]), false);
  assert.equal(safety.resultOk([{ ...clean, steps: [{ ok: true, skipped: true }] }]), false);
  assert.equal(safety.resultOk([{ ...clean, knownIssues: [{ id: 'typing-only-room-stuck-after-answer', workaround: 'reload' }] }]), false);
  assert.equal(safety.resultOk([clean]), true);
});


// ---- approved-environment adapter (lib/isolation.mjs): every condition must hold, nothing is merely asserted
import { ephemeralRunnerViolations, requireEphemeralRunner } from '../lib/isolation.mjs';

const GOOD = { MIRROR_QA_GITHUB_HOSTED: '1', GITHUB_ACTIONS: 'true', RUNNER_ENVIRONMENT: 'github-hosted',
  NEXT_PUBLIC_SUPABASE_URL: 'http://127.0.0.1:54399', NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8099' };
const clean = { root: '/repo', exists: () => false, list: () => [] };

test('an ephemeral secret-free GitHub-hosted runner is approved', () => {
  assert.deepEqual(ephemeralRunnerViolations({ env: GOOD, ...clean }), []);
  assert.doesNotThrow(() => requireEphemeralRunner({ env: GOOD, ...clean }));
});

test('every missing or contradicting condition blocks execution', () => {
  const cases = [
    [{ ...GOOD, MIRROR_QA_GITHUB_HOSTED: undefined }, /MIRROR_QA_GITHUB_HOSTED/],
    [{ ...GOOD, GITHUB_ACTIONS: undefined }, /GitHub Actions/],
    [{ ...GOOD, RUNNER_ENVIRONMENT: 'self-hosted' }, /GitHub-hosted/],
    [{ ...GOOD, SUPABASE_SERVICE_ROLE_KEY: 'x' }, /SUPABASE_SERVICE_ROLE_KEY/],
    [{ ...GOOD, SARVAM_API_KEY: 'x' }, /SARVAM_API_KEY/],
    [{ ...GOOD, NEXT_PUBLIC_SUPABASE_URL: 'https://project.supabase.co' }, /loopback/],
    [{ ...GOOD, NEXT_PUBLIC_API_URL: 'https://api.example.com' }, /loopback/],
  ];
  for (const [env, expected] of cases) assert.throws(() => requireEphemeralRunner({ env, ...clean }), (e) => /BLOCKED/.test(e.message) && expected.test(e.message));
});

test('a dotenv file anywhere in the product tree blocks execution, the template does not', () => {
  const withEnv = { root: '/repo', exists: () => true, list: (dir) => (dir === '/repo' ? ['.env', '.env.example'] : []) };
  assert.match(ephemeralRunnerViolations({ env: GOOD, ...withEnv }).join(), /dotenv file present: \.env/);
  const templateOnly = { root: '/repo', exists: () => true, list: () => ['.env.example'] };
  assert.deepEqual(ephemeralRunnerViolations({ env: GOOD, ...templateOnly }), []);
});

test('a developer machine is never approved, whatever the caller passes', () => {
  assert.throws(() => requireEphemeralRunner({ env: { PATH: 'x' }, ...clean }), /BLOCKED/);
});

test('the CI runner script never reads secrets and checks isolation before listening or building', () => {
  const source = fs.readFileSync(new URL('../run-ci.mjs', import.meta.url), 'utf8');
  assert.ok(source.indexOf('requireEphemeralRunner()') < source.indexOf('startMock('));
  assert.doesNotMatch(source, /process\.env\.(SUPABASE|SARVAM|DEEPGRAM|OPENAI|ANTHROPIC)/);
  assert.match(source, /127\.0\.0\.1/);
});
