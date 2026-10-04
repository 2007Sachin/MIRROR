// Defense in depth, NOT an OS/SSR/build isolation boundary.
export async function installBrowserRail(context, origins, deniedRequests) {
  const allowed = new Set(origins);
  for (const origin of allowed) {
    const parsed = new URL(origin);
    if (parsed.origin !== origin || parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1') throw new Error('Invalid QA origin');
  }
  if (!allowed.size || typeof context.routeWebSocket !== 'function') throw new Error('Browser network rail unavailable');
  const originOf = value => { try { return new URL(value).origin; } catch { return 'invalid'; } };
  await context.route('**/*', async route => {
    const origin = originOf(route.request().url());
    if (allowed.has(origin)) return route.continue();
    deniedRequests.push({ kind: 'http', origin }); // never query strings/tokens
    return route.abort('blockedbyclient');
  });
  await context.routeWebSocket('**/*', socket => {
    deniedRequests.push({ kind: 'websocket', origin: originOf(socket.url()) });
    socket.close(); // critical path needs no websocket; never connectToServer
  });
}
