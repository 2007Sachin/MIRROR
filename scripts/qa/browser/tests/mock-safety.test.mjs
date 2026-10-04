import test from 'node:test';
import assert from 'node:assert/strict';
import * as safety from '../lib/safety.mjs';
import fs from 'node:fs';
import * as mock from '../mock/server.mjs';

test('partial startup closes both servers when second bind fails without sockets', async () => {
  assert.equal(typeof mock.bindMockServers, 'function', 'missing partial-start cleanup');
  const closed = [];
  const servers = ['auth', 'api'].map(name => ({ closeAllConnections() {}, close(done) { closed.push(name); done(); } }));
  let calls = 0;
  const listen = async () => { if (++calls === 2) throw new Error('synthetic bind failure'); return 39211; };
  await assert.rejects(mock.bindMockServers(servers, [39211, 39212], listen), /synthetic bind failure/);
  assert.deepEqual(closed.sort(), ['api', 'auth']);
});

test('both mock listeners authorize before CORS or route dispatch', () => {
  const source = fs.readFileSync(new URL('../mock/server.mjs', import.meta.url), 'utf8');
  assert.equal((source.match(/if \(!guardRequest\(request, response,/g) ?? []).length, 2);
  assert.match(source, /controlToken,/);
  assert.doesNotMatch(source, /access-control-request-headers.*\?\?/);
});

test('mock Host, Origin, and control token are fail-closed', () => {
  assert.equal(typeof safety.authorizeMockRequest, 'function', 'missing mock request guard');
  const policy = { host: '127.0.0.1:39212', origins: ['http://127.0.0.1:3000'], controlToken: 'synthetic-test-token' };
  const req = (headers, url = '/api/v1/me') => ({ headers, url });
  assert.equal(safety.authorizeMockRequest(req({ host: policy.host }), policy), true);
  assert.equal(safety.authorizeMockRequest(req({ host: 'evil.invalid' }), policy), false);
  assert.equal(safety.authorizeMockRequest(req({ host: policy.host, origin: 'http://evil.invalid' }), policy), false);
  assert.equal(safety.authorizeMockRequest(req({ host: policy.host, origin: policy.origins[0] }), policy), true);
  assert.equal(safety.authorizeMockRequest(req({ host: policy.host }, '/__qa/reset'), policy), false);
  assert.equal(safety.authorizeMockRequest(req({ host: policy.host, 'x-qa-control-token': 'wrong' }, '/__qa/state'), policy), false);
  assert.equal(safety.authorizeMockRequest(req({ host: policy.host, 'x-qa-control-token': policy.controlToken }, '/__qa/state'), policy), true);
});
