import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
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
