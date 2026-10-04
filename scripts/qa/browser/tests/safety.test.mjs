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

