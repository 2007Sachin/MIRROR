import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createCollector } from '../lib/collector.mjs';
const url = new URL('../lib/network.mjs', import.meta.url);
const rail = fs.existsSync(url) ? await import(url.href) : {};

test('critical path blocks service workers and attaches rail before a page exists', () => {
  const source = fs.readFileSync(new URL('./critical-path.mjs', import.meta.url), 'utf8');
  assert.match(source, /serviceWorkers: ['"]block['"]/);
  assert.ok(source.indexOf('await installBrowserRail(') < source.indexOf('await context.newPage()'));
  assert.match(source, /findings.deniedRequests = deniedRequests/);
});

test('browser rail permits only exact QA origins and denies all websockets', async () => {
  assert.equal(typeof rail.installBrowserRail, 'function', 'missing browser deny rail');
  let route, ws;
  const context = { async route(pattern, handler) { assert.equal(pattern, '**/*'); route = handler; }, async routeWebSocket(pattern, handler) { assert.equal(pattern, '**/*'); ws = handler; } };
  const denied = [];
  await rail.installBrowserRail(context, ['http://127.0.0.1:3000', 'http://127.0.0.1:39212'], denied);
  for (const [url, allowed] of [['http://127.0.0.1:3000/path', true], ['http://127.0.0.1:39212/api', true], ['http://127.0.0.1:3001/', false], ['http://localhost:3000/', false], ['https://evil.invalid/?secret=synthetic', false], ['http://127.0.0.1:3000@evil.invalid/', false]]) {
    let action;
    await route({ request: () => ({ url: () => url }), abort: async () => { action = 'deny'; }, continue: async () => { action = 'allow'; } });
    assert.equal(action, allowed ? 'allow' : 'deny');
  }
  let closed = false;
  ws({ url: () => 'ws://127.0.0.1:3000/', close: () => { closed = true; } });
  assert.equal(closed, true);
  assert.equal(denied.length, 5);
  assert.ok(denied.every(item => !JSON.stringify(item).includes('secret')));
});

test('only the optional target-create 503 in T16 is an expected browser error', () => {
  const observe = (step, requestUrl, status, consoleText) => {
    const listeners = {};
    const page = { on: (event, handler) => { listeners[event] = handler; }, url: () => 'http://127.0.0.1:3099/roles/new' };
    const collector = createCollector();
    collector.setStep(step);
    collector.attach(page);
    listeners.response({ status: () => status, url: () => requestUrl });
    listeners.console({ type: () => 'error', text: () => consoleText });
    return collector.findings();
  };
  const step = 't16-onboarding-continues-with-general-plan-without-target';
  const apiUrl = 'http://127.0.0.1:8099/api/v1/targets';
  const message = 'Failed to load resource: the server responded with a status of 503 (Service Unavailable)';

  const expected = observe(step, apiUrl, 503, message);
  assert.deepEqual(expected.badResponses, []);
  assert.deepEqual(expected.consoleErrors, []);

  const wrongStep = observe('t01-role-step-target-fields', apiUrl, 503, message);
  assert.equal(wrongStep.badResponses.length, 1);
  assert.equal(wrongStep.consoleErrors.length, 1);
  const wrongPath = observe(step, `${apiUrl}/unexpected`, 503, message);
  assert.equal(wrongPath.badResponses.length, 1);
  const wrongStatus = observe(step, apiUrl, 500, 'Failed to load resource: the server responded with a status of 500 (Internal Server Error)');
  assert.equal(wrongStatus.badResponses.length, 1);
  assert.equal(wrongStatus.consoleErrors.length, 1);
});


test('only the candidate stage stale-save conflict in T02b is expected', () => {
  const observe = (step, requestUrl, status, method, consoleText) => {
    const listeners = {};
    const page = { on: (event, handler) => { listeners[event] = handler; }, url: () => 'http://127.0.0.1:3099/plan' };
    const collector = createCollector();
    collector.setStep(step);
    collector.attach(page);
    listeners.response({ status: () => status, url: () => requestUrl, request: () => ({ method: () => method }) });
    listeners.console({ type: () => 'error', text: () => consoleText });
    return collector.findings();
  };
  const step = 't02b-stage-practice-review-and-stage-removal';
  const url = 'http://127.0.0.1:8099/api/v1/targets/00000000-0000-4000-8000-000000000311/blueprint/stages';
  const message = 'Failed to load resource: the server responded with a status of 409 (Conflict)';
  const expected = observe(step, url, 409, 'PUT', message);
  assert.deepEqual(expected.badResponses, []);
  assert.deepEqual(expected.consoleErrors, []);
  assert.equal(observe(step, url, 409, 'GET', message).badResponses.length, 1, 'wrong method is not allowed');
  assert.equal(observe('t09-round-detail', url, 409, 'PUT', message).badResponses.length, 1, 'wrong step is not allowed');
  assert.equal(observe(step, url.replace('/blueprint/stages', '/blueprint'), 409, 'PUT', message).badResponses.length, 1, 'wrong path is not allowed');
  assert.equal(observe(step, url, 500, 'PUT', 'Failed to load resource: the server responded with a status of 500 (Internal Server Error)').badResponses.length, 1, 'wrong status is not allowed');
});

test('only the other-family round 404 in T18 is expected; any other round or step still fails', () => {
  const observe = (step, requestUrl, status, consoleText) => {
    const listeners = {};
    const page = { on: (event, handler) => { listeners[event] = handler; }, url: () => 'http://127.0.0.1:3099/plan/rounds/coding_reasoning' };
    const collector = createCollector();
    collector.setStep(step);
    collector.attach(page);
    listeners.response({ status: () => status, url: () => requestUrl });
    listeners.console({ type: () => 'error', text: () => consoleText });
    return collector.findings();
  };
  const step = 't18-business-roles-round-detail';
  const url = 'http://127.0.0.1:8099/api/v1/targets/00000000-0000-4000-8000-000000000301/rounds/coding_reasoning';
  const message = 'Failed to load resource: the server responded with a status of 404 (Not Found)';
  const expected = observe(step, url, 404, message);
  assert.deepEqual(expected.badResponses, []);
  assert.deepEqual(expected.consoleErrors, []);
  assert.equal(observe('t19-business-roles-practice-to-review', url, 404, message).badResponses.length, 1);
  assert.equal(observe(step, url.replace('coding_reasoning', 'business_problem_solving'), 404, message).badResponses.length, 1);
  assert.equal(observe(step, url, 500, 'Failed to load resource: the server responded with a status of 500 (Internal Server Error)').consoleErrors.length, 1);
});
