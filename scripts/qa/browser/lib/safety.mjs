// Browser routing is not an SSR/build egress boundary. No approved adapter exists.
// Intentionally has no env/flag override: unsupported execution must not proceed.
export function parseArgs(args) {
  const result = { build: false, only: undefined };
  const seen = new Set();
  for (const arg of args) {
    const key = arg.split('=')[0];
    if (seen.has(key)) throw new Error(`Duplicate option: ${key}`);
    seen.add(key);
    if (arg === '--build') result.build = true;
    else if (arg.startsWith('--only=')) {
      const only = arg.slice(7);
      if (!['desktop', 'mobile'].includes(only)) throw new Error('Invalid --only: expected desktop or mobile');
      result.only = only;
    } else throw new Error(`Unknown option: ${arg}`);
  }
  return result;
}

export function resultOk(viewports) {
  return Array.isArray(viewports) && viewports.length > 0 && viewports.every(view =>
    Array.isArray(view.steps) && view.steps.length > 0 && view.steps.every(step => step.ok === true && !step.skipped)
    && view.knownIssues?.length === 0
    && ['pageErrors', 'consoleErrors', 'failedRequests', 'badResponses', 'deniedRequests'].every(key =>
      key === 'deniedRequests' ? (view.findings?.[key]?.length ?? 0) === 0 : view.findings?.[key]?.length === 0)
    && view.unmockedApiCalls?.length === 0);
}

export function authorizeMockRequest(request, policy) {
  if (!policy?.host || request.headers.host !== policy.host) return false;
  const origin = request.headers.origin;
  if (origin !== undefined && !policy.origins.includes(origin)) return false;
  let pathname;
  try { pathname = new URL(request.url, 'http://127.0.0.1').pathname; } catch { return false; }
  if (pathname.startsWith('/__qa/')) {
    return typeof policy.controlToken === 'string' && policy.controlToken.length > 0
      && request.headers['x-qa-control-token'] === policy.controlToken;
  }
  return true;
}

export function requireSupportedIsolation() {
  throw new Error('BLOCKED: independent SSR and build egress isolation is not implemented or approved; browser/build execution is disabled.');
}
