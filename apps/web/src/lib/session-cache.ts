import { getSupabaseBrowserClient } from "@/lib/supabase";

/**
 * Browser-session cache for the few reads every authenticated page repeats (the profile
 * and the active role behind the app shell). Each page mounts its own shell, so without
 * this the shell would refetch and redraw on every navigation.
 * Cleared on sign-in, sign-out or account change; failed reads are never kept.
 */
type Entry = { value?: unknown; promise?: Promise<unknown> };

const store = new Map<string, Entry>();
let listening = false;

function listen() {
  if (listening || typeof window === "undefined") return;
  listening = true;
  getSupabaseBrowserClient().auth.onAuthStateChange((event) => {
    if (event === "SIGNED_OUT" || event === "SIGNED_IN" || event === "USER_UPDATED") store.clear();
  });
}

export function peekCached<T>(key: string): T | undefined {
  return store.get(key)?.value as T | undefined;
}

export function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  listen();
  const entry = store.get(key);
  if (entry?.promise) return entry.promise as Promise<T>;
  const promise = load().then(
    (value) => {
      if (store.get(key)?.promise === promise) store.set(key, { value, promise });
      return value;
    },
    (reason: unknown) => {
      if (store.get(key)?.promise === promise) store.delete(key);
      throw reason;
    },
  );
  store.set(key, { promise });
  return promise;
}

export function setCached<T>(key: string, value: T) {
  store.set(key, { value, promise: Promise.resolve(value) });
}

export function invalidateCached(key: string) {
  store.delete(key);
}
