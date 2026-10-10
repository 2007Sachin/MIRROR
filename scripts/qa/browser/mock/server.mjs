// Hermetic fake of Supabase Auth + the Mirror API for browser QA. Dependency-free Node ESM.
//
// Two real HTTP servers on 127.0.0.1 (the web app calls them from the browser AND from Next
// server components/middleware, so page.route() interception would not be enough):
//   auth server: the subset of GoTrue the web app uses (password + refresh-token grants, /user,
//                /logout, JWKS). Tokens are ES256 JWTs signed with a per-run in-memory key.
//   api server : the Mirror API endpoints on the candidate critical path, in-memory and stateful.
// Response bodies come from ./fixtures/*.json, which tests/unit/test_qa_mock_contract.py
// validates against the real backend pydantic models. Anything not implemented answers 404 and
// is recorded in state.unmocked so the browser test fails loudly instead of passing by accident.
import { authorizeMockRequest } from "../lib/safety.mjs";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createTargetsMock, QA_BUSINESS_CASE_PROMPTS, QA_RESEARCHED_CODING_PROMPTS } from "./targets.mjs";

const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const LOOPBACK = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

export const QA_EMAIL = "qa-synthetic@mirror-qa.invalid";
export const QA_NAME = "QA Synthetic (test only)";
export const IDS = {
  user: "00000000-0000-4000-8000-000000000001",
  role: "00000000-0000-4000-8000-000000000002",
  session: "00000000-0000-4000-8000-000000000101",
};
const KID = "qa-mock-key";
const TOKEN_TTL_SECONDS = 3600;

const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), "utf8"));
export function reportForSession(reportFixture, session, turns) {
  const value = JSON.parse(JSON.stringify(reportFixture));
  value.session.target_role = session.target_role;
  value.session.completed_at = session.completed_at;
  const firstAnswer = turns.find((turn) => turn.speaker === "CANDIDATE");
  for (const quote of value.skill_assessments[0]?.evidence ?? []) quote.turn_id = firstAnswer?.id ?? null;
  return value;
}
const turnId = (index) => `00000000-0000-4000-8000-${String(200 + index).padStart(12, "0")}`;
const sha = (value) => crypto.createHash("sha256").update(String(value)).digest();

/** Refuses anything that could reach beyond this machine or look like a production run. */
export function assertHermetic({ supabaseUrl, apiUrl, env = process.env }) {
  if (env.NODE_ENV === "production") throw new Error("qa-mock: refusing to start with NODE_ENV=production");
  for (const [name, value] of [["NEXT_PUBLIC_SUPABASE_URL", supabaseUrl], ["NEXT_PUBLIC_API_URL", apiUrl]]) {
    let host;
    try {
      host = new URL(value).hostname;
    } catch {
      throw new Error(`qa-mock: ${name} is not a valid URL`);
    }
    if (!LOOPBACK.has(host)) throw new Error(`qa-mock: ${name} host "${host}" is not loopback; refusing to start`);
  }
}

export async function bindMockServers(servers, ports, bind = listen) {
  try {
    const bound = [];
    for (let i = 0; i < servers.length; i += 1) bound.push(await bind(servers[i], ports[i]));
    return bound;
  } catch (error) {
    await Promise.all(servers.map(server => new Promise(resolve => {
      server.closeAllConnections?.();
      server.close(() => resolve());
    })));
    throw error;
  }
}

function listen(server, port) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server.address().port));
  });
}

const readBody = (request) =>
  new Promise((resolve) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8");
      try {
        resolve(text ? JSON.parse(text) : null);
      } catch {
        resolve(undefined); // malformed JSON
      }
    });
  });

function send(request, response, status, body, extra = {}) {
  const origin = request.headers.origin;
  const headers = {
    "content-type": "application/json",
    "cache-control": "no-store",
    // Reflect rather than "*": Chrome does not count "*" as covering the Authorization header.
    ...(origin ? { "access-control-allow-origin": origin, vary: "Origin", "access-control-allow-credentials": "true" } : {}),
    ...extra,
  };
  response.writeHead(status, headers);
  response.end(status === 204 || body === undefined ? undefined : JSON.stringify(body));
}

function preflight(request, response) {
  const origin = request.headers.origin ?? "";
  response.writeHead(204, {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "access-control-allow-headers": "authorization,content-type",
    "access-control-max-age": "600",
    vary: "Origin",
  });
  response.end();
}

export async function startMock({ authPort = 0, apiPort = 0, password, supabaseUrl, apiUrl, allowedOrigins = [] } = {}) {
  const controlToken = crypto.randomBytes(32).toString("base64url");
  for (const origin of allowedOrigins) {
    const parsed = new URL(origin);
    if (parsed.origin !== origin || parsed.protocol !== "http:" || parsed.hostname !== "127.0.0.1") throw new Error("qa-mock: invalid allowed origin");
  }
  function guardRequest(request, response, server) {
    const port = server.address()?.port;
    const policy = { host: `127.0.0.1:${port}`, origins: allowedOrigins, controlToken };
    if (authorizeMockRequest(request, policy)) return true;
    response.writeHead(403, { "content-type": "application/json", "cache-control": "no-store" });
    response.end(JSON.stringify({ detail: "qa-mock: forbidden request" }));
    return false;
  }
  // Guard first, before anything binds a socket.
  assertHermetic({
    supabaseUrl: supabaseUrl ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://127.0.0.1",
    apiUrl: apiUrl ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1",
  });
  if (!password) throw new Error("qa-mock: a password must be supplied in memory (never from a file)");
  const passwordHash = sha(password);
  const clock = () => new Date().toISOString();

  // ----------------------------------------------------------------------------- auth
  const { privateKey, publicKey } = crypto.generateKeyPairSync("ec", { namedCurve: "P-256" });
  const jwk = { ...publicKey.export({ format: "jwk" }), kid: KID, alg: "ES256", use: "sig" };
  const b64u = (value) => Buffer.from(value).toString("base64url");
  const authSessions = new Map(); // auth session id -> { refreshToken, revoked }
  let authSessionCounter = 0;
  let authBase = "";

  const userObject = () => ({
    id: IDS.user,
    aud: "authenticated",
    role: "authenticated",
    email: QA_EMAIL,
    email_confirmed_at: "2026-01-01T00:00:00Z",
    phone: "",
    confirmed_at: "2026-01-01T00:00:00Z",
    last_sign_in_at: clock(),
    app_metadata: { provider: "email", providers: ["email"] },
    user_metadata: { synthetic: true, full_name: QA_NAME, email_verified: true },
    identities: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    is_anonymous: false,
  });

  function signJwt(claims) {
    const head = b64u(JSON.stringify({ alg: "ES256", typ: "JWT", kid: KID }));
    const body = b64u(JSON.stringify(claims));
    const signature = crypto.sign("sha256", Buffer.from(`${head}.${body}`), { key: privateKey, dsaEncoding: "ieee-p1363" });
    return `${head}.${body}.${b64u(signature)}`;
  }

  function verifyJwt(token) {
    const parts = String(token ?? "").split(".");
    if (parts.length !== 3) return null;
    try {
      const valid = crypto.verify("sha256", Buffer.from(`${parts[0]}.${parts[1]}`), { key: publicKey, dsaEncoding: "ieee-p1363" }, Buffer.from(parts[2], "base64url"));
      if (!valid) return null;
      const claims = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8"));
      if (claims.exp * 1000 < Date.now()) return null;
      if (authSessions.get(claims.session_id)?.revoked) return null;
      return claims;
    } catch {
      return null;
    }
  }

  function issueSession(existingId) {
    const sessionId = existingId ?? `00000000-0000-4000-8000-${String(900 + ++authSessionCounter).padStart(12, "0")}`;
    const refreshToken = crypto.randomBytes(12).toString("base64url");
    authSessions.set(sessionId, { refreshToken, revoked: false });
    const issuedAt = Math.floor(Date.now() / 1000);
    const user = userObject();
    const accessToken = signJwt({
      iss: `${authBase}/auth/v1`,
      aud: "authenticated",
      sub: IDS.user,
      email: QA_EMAIL,
      role: "authenticated",
      aal: "aal1",
      amr: [{ method: "password", timestamp: issuedAt }],
      session_id: sessionId,
      iat: issuedAt,
      exp: issuedAt + TOKEN_TTL_SECONDS,
      app_metadata: user.app_metadata,
      user_metadata: user.user_metadata,
      is_anonymous: false,
    });
    return { access_token: accessToken, token_type: "bearer", expires_in: TOKEN_TTL_SECONDS, expires_at: issuedAt + TOKEN_TTL_SECONDS, refresh_token: refreshToken, user };
  }

  const authLog = [];
  const authServer = http.createServer(async (request, response) => {
    if (!guardRequest(request, response, authServer)) return;
    const url = new URL(request.url, "http://x");
    if (request.method === "OPTIONS") return preflight(request, response);
    authLog.push(`${request.method} ${url.pathname}`);
    const bearer = /^Bearer (.+)$/.exec(request.headers.authorization ?? "")?.[1];
    const body = request.method === "POST" ? await readBody(request) : null;

    if (request.method === "POST" && url.pathname === "/auth/v1/token") {
      const grant = url.searchParams.get("grant_type");
      if (grant === "password") {
        const ok = body && body.email === QA_EMAIL && crypto.timingSafeEqual(sha(body.password ?? ""), passwordHash);
        if (!ok) return send(request, response, 400, { code: 400, error_code: "invalid_credentials", msg: "Invalid login credentials" });
        return send(request, response, 200, issueSession());
      }
      if (grant === "refresh_token") {
        const entry = [...authSessions.entries()].find(([, value]) => value.refreshToken === body?.refresh_token && !value.revoked);
        if (!entry) return send(request, response, 400, { code: 400, error_code: "refresh_token_not_found", msg: "Invalid Refresh Token: Refresh Token Not Found" });
        return send(request, response, 200, issueSession(entry[0]));
      }
      return send(request, response, 400, { code: 400, error_code: "validation_failed", msg: "unsupported grant_type" });
    }
    if (request.method === "GET" && url.pathname === "/auth/v1/user") {
      return verifyJwt(bearer)
        ? send(request, response, 200, userObject())
        : send(request, response, 401, { code: 401, error_code: "bad_jwt", msg: "invalid JWT" });
    }
    if (request.method === "POST" && url.pathname === "/auth/v1/logout") {
      const claims = verifyJwt(bearer);
      if (claims) authSessions.get(claims.session_id).revoked = true;
      return send(request, response, 204);
    }
    if (request.method === "GET" && url.pathname === "/auth/v1/.well-known/jwks.json") {
      return send(request, response, 200, { keys: [jwk] });
    }
    state.unmocked.push(`AUTH ${request.method} ${url.pathname}`);
    return send(request, response, 404, { code: 404, error_code: "not_found", msg: "qa-mock: unmocked auth endpoint" });
  });

  // ----------------------------------------------------------------------------- api state
  const state = {
    unmocked: [],
    requests: [],
    session: null,
    turns: [],
    ended: false,
    createBodies: [],
    heartbeats: 0,
    answers: [],
    idempotency: new Map(),
    clientTurns: new Map(),
  };
  const QUESTIONS = [
    { text: "Hello, this is a short synthetic practice.\n\nTell me about one project you worked on.", type: "PLANNED" },
    { text: "What was your own part in it?", type: "DEPTH_PROBE" },
    { text: "What changed because of that work?", type: "PLANNED" },
  ];
  let activeQuestions = QUESTIONS;
  const CLOSING = "Thank you. That is the end of this short practice.";
  const questionsAsked = () => state.turns.filter((turn) => turn.speaker === "INTERVIEWER" && turn.turn_type !== "CLOSING").length;
  const remaining = () => Math.max(0, 300 - (state.session?.elapsed_seconds ?? 0));

  function addInterviewerTurn() {
    const asked = questionsAsked();
    const closing = asked >= activeQuestions.length;
    const turn = {
      ...fixture("turn.json"),
      id: turnId(state.turns.length + 1),
      session_id: state.session.id,
      turn_index: state.turns.length + 1,
      speaker: "INTERVIEWER",
      text: closing ? CLOSING : activeQuestions[asked].text,
      turn_type: closing ? "CLOSING" : activeQuestions[asked].type,
      phase: closing ? "CLOSING" : "PROJECTS",
      created_at: clock(),
    };
    state.turns.push(turn);
    state.session.updated_at = clock();
    return turn;
  }

  const voiceFor = (turn) => ({
    ...fixture("voice_turn.json"),
    session_id: state.session.id,
    turn_id: turn.id,
    question_text: turn.text,
    turn_index: turn.turn_index,
    phase: turn.phase,
    turn_type: turn.turn_type,
    remaining_time_seconds: remaining(),
  });

  const assessment = () => ({
    ...fixture("assessment.json"),
    session_id: state.session.id,
    status: state.ended ? "COMPLETED" : "PENDING",
    queued_at: state.ended ? state.session.completed_at : null,
    started_at: state.ended ? state.session.completed_at : null,
    completed_at: state.ended ? state.session.completed_at : null,
  });

  const home = () => {
    if (!state.session) return fixture("home_first_practice.json");
    const s = state.session;
    if (state.ended) {
      const value = fixture("home_review_ready.json");
      value.review.session_id = s.id;
      value.review.finished_at = s.completed_at;
      value.progress.last_practised_at = s.completed_at;
      value.activity[0].session_id = s.id;
      value.activity[0].at = s.completed_at;
      return value;
    }
    const value = fixture("home_active_practice.json");
    value.active.session_id = s.id;
    value.active.kind = s.status === "ACTIVE" ? "ACTIVE" : "READY";
    value.active.question_number = Math.min(questionsAsked(), activeQuestions.length);
    value.active.last_active_at = s.updated_at;
    return value;
  };

  const dashboard = () => {
    if (!state.session) return fixture("dashboard_empty.json");
    const s = state.session;
    return {
      current: {
        ...fixture("dashboard_diagnostic.json"),
        id: s.id,
        interview_status: s.status,
        phase: s.phase,
        completed_at: s.completed_at,
        assessment: state.ended ? assessment() : null,
        diagnostic_available: state.ended,
        updated_at: s.updated_at,
      },
      previous: [],
    };
  };

  const review = () => ({ ...fixture("review.json"), session_id: state.session.id, completed_at: state.session.completed_at });
  const report = () => reportForSession(fixture("report.json"), state.session, state.turns);

  // ----------------------------------------------------------------------------- api routes
  const err = (status, detail) => ({ status, body: { detail } });
  const needSession = (id) => (state.session && state.session.id === id ? null : err(404, "Session not found"));
  const routes = [];
  const route = (method, pattern, handler) => routes.push({ method, pattern: new RegExp(`^${pattern}$`), handler });

  route("GET", "/api/v1/me", () => ({ body: fixture("profile.json") }));
  route("GET", "/api/v1/onboarding", () => ({ body: fixture("onboarding.json") }));
  route("GET", "/api/v1/active-role", () => ({ body: fixture("active_role.json") }));
  route("GET", "/api/v1/home", () => ({ body: home() }));
  route("GET", "/api/v1/dashboard", () => ({ body: dashboard() }));
  route("GET", "/api/v1/dashboard/summary", () => ({ body: { latest_review: state.ended ? review() : null } }));
  route("GET", `/api/v1/roles/${IDS.role}/practice-recommendation`, () => ({ body: { recommendation: null } }));

  // One place that creates the (single) mock session, for POST /api/sessions and round practice.
  function createSession(body) {
    const created = clock();
    const qaSets = { qa_researched_coding: QA_RESEARCHED_CODING_PROMPTS, qa_business_case: QA_BUSINESS_CASE_PROMPTS };
    activeQuestions = qaSets[body.qa_prompt_set]
      ? qaSets[body.qa_prompt_set].map(({ text, type }) => ({ text, type }))
      : QUESTIONS;
    state.session = {
      ...fixture("session.json"),
      target_role: body.target_role,
      role_profile_id: body.role_profile_id ?? null,
      practice_mode: body.practice_mode ?? "FULL_INTERVIEW",
      practice_focus: body.practice_focus ?? null,
      practice_theme: body.practice_theme ?? null,
      created_at: created,
      updated_at: created,
      phase_started_at: created,
    };
    state.turns = [];
    state.ended = false;
    if (body.idempotency_key) state.idempotency.set(body.idempotency_key, state.session.id);
    return state.session;
  }

  route("POST", "/api/sessions", ({ body }) => {
    if (!body || typeof body.target_role !== "string" || body.target_role.length < 2) return err(422, "target_role is required");
    const mode = body.practice_mode ?? "FULL_INTERVIEW";
    if (!["FULL_INTERVIEW", "FOCUSED_PRACTICE", "QUICK_DRILL"].includes(mode)) return err(422, "unknown practice_mode");
    if (mode !== "FULL_INTERVIEW" && !body.practice_focus) return err(422, "a focused practice or quick drill needs one area to work on");
    state.createBodies.push(body);
    if (body.idempotency_key && state.idempotency.has(body.idempotency_key)) return { status: 201, body: state.session };
    return { status: 201, body: createSession({ ...body, practice_mode: mode }) };
  });
  route("POST", "/api/v1/sessions/([^/]+)/documents", ({ match, body }) => {
    const missing = needSession(match[1]);
    if (missing) return missing;
    if (!Array.isArray(body?.document_ids) || !body.document_ids.length) return err(422, "document_ids is required");
    return { body: state.session };
  });
  route("POST", "/api/(?:v1/)?sessions/([^/]+)/prepare", ({ match }) => {
    const missing = needSession(match[1]);
    if (missing) return missing;
    Object.assign(state.session, { status: "READY", total_questions: activeQuestions.length, updated_at: clock() });
    return { body: { ...fixture("prepare.json"), session: state.session } };
  });
  route("GET", "/api/(?:v1/)?sessions/([^/]+)", ({ match }) => needSession(match[1]) ?? { body: state.session });
  route("POST", "/api/v1/sessions/([^/]+)/voice/start", ({ match }) => {
    const missing = needSession(match[1]);
    if (missing) return missing;
    if (!["READY", "ACTIVE"].includes(state.session.status)) return err(409, "This session cannot be started.");
    if (state.session.status === "READY") Object.assign(state.session, { status: "ACTIVE", started_at: clock(), phase: "PROJECTS" });
    const last = state.turns.at(-1);
    return { body: voiceFor(last?.speaker === "INTERVIEWER" ? last : addInterviewerTurn()) };
  });
  route("POST", "/api/v1/sessions/([^/]+)/turn-text", ({ match, body }) => {
    const missing = needSession(match[1]);
    if (missing) return missing;
    if (typeof body?.text !== "string" || !body.text.trim() || body.text.length > 20000) return err(422, "text must be 1-20000 characters");
    if (state.session.status !== "ACTIVE") return err(409, "This conversation is not active.");
    const replay = state.clientTurns.get(body.client_turn_id);
    if (replay) return { body: replay };
    if (state.turns.at(-1)?.speaker !== "INTERVIEWER") return err(409, "It is not your turn.");
    state.answers.push(body.text);
    state.turns.push({
      ...fixture("turn.json"),
      id: turnId(state.turns.length + 1),
      session_id: state.session.id,
      turn_index: state.turns.length + 1,
      speaker: "CANDIDATE",
      text: body.text.trim(),
      turn_type: "PLANNED",
      phase: "PROJECTS",
      created_at: clock(),
    });
    state.session.elapsed_seconds += 20;
    const candidateIndex = state.turns.length;
    const next = addInterviewerTurn();
    const result = {
      ...fixture("text_turn.json"),
      session_id: state.session.id,
      candidate_turn_index: candidateIndex,
      interviewer_turn_index: next.turn_index,
      question_text: next.text,
      phase: next.phase,
      turn_type: next.turn_type,
      remaining_time_seconds: remaining(),
    };
    state.clientTurns.set(body.client_turn_id, result);
    return { body: result };
  });
  route("GET", "/api/v1/sessions/([^/]+)/turns", ({ match }) => needSession(match[1]) ?? { body: state.turns });
  route("POST", "/api/v1/sessions/([^/]+)/heartbeat", ({ match, body }) => {
    const missing = needSession(match[1]);
    if (missing) return missing;
    if (typeof body?.lease_id !== "string" || body.lease_id.length < 8) return err(422, "lease_id is required");
    state.heartbeats += 1;
    return { body: { ok: true } };
  });
  route("POST", "/api/v1/sessions/([^/]+)/pause", ({ match }) => needSession(match[1]) ?? { body: { paused: true, remaining_time_seconds: remaining() } });
  route("POST", "/api/(?:v1/)?sessions/([^/]+)/end", ({ match }) => {
    const missing = needSession(match[1]);
    if (missing) return missing;
    if (!state.ended) {
      state.ended = true;
      Object.assign(state.session, { status: "COMPLETED", phase: "COMPLETE", completed_at: clock(), updated_at: clock() });
    }
    return { body: { ...fixture("completion.json"), ...state.session, assessment: assessment() } };
  });
  route("GET", "/api/v1/sessions/([^/]+)/assessment", ({ match }) => needSession(match[1]) ?? { body: assessment() });
  const notReady = { code: "ASSESSMENT_NOT_READY", message: "Your review is still being prepared." };
  route("GET", "/api/v1/sessions/([^/]+)/report", ({ match }) => needSession(match[1]) ?? (state.ended ? { body: report() } : err(409, notReady)));
  route("GET", "/api/v1/sessions/([^/]+)/review", ({ match }) => needSession(match[1]) ?? (state.ended ? { body: review() } : err(409, notReady)));
  route("GET", "/api/v1/sessions/([^/]+)/attempts", ({ match }) => needSession(match[1]) ?? { body: [] });
  route("GET", "/api/v1/sessions/([^/]+)/story-suggestions", ({ match }) => needSession(match[1]) ?? { body: [] });

  // Loop 2: interview targets, plan and role-setup endpoints (./targets.mjs), with scenarios.
  const targets = createTargetsMock({
    fixture, clock, createSession, roleId: IDS.role, roleName: fixture("active_role.json").role?.target_role ?? "QA Analyst (test role)",
  });
  for (const [method, pattern, handler] of targets.routes) route(method, pattern, handler);

  // Test-control surface (not part of the Mirror API). Read-only except reset and scenario.
  route("POST", "/__qa/scenario", ({ body }) => targets.setScenario(body));
  route("POST", "/__qa/targets/reset", () => {
    targets.reset();
    return { body: { ok: true } };
  });
  route("GET", "/__qa/state", () => ({
    body: {
      sessionStatus: state.session?.status ?? null,
      ended: state.ended,
      turns: state.turns.length,
      answers: state.answers,
      createBodies: state.createBodies,
      heartbeats: state.heartbeats,
      unmocked: state.unmocked,
      authLog,
      requests: state.requests,
      targets: {
        scenario: targets.state.scenario,
        creates: targets.state.targetCreates,
        roundPractice: targets.state.roundPracticeBodies,
        roundPracticeResponses: targets.state.roundPracticeResponses,
        candidateStagePlanPins: [...targets.state.stagePlans.entries()].map(([target_id, plan]) => ({ target_id, version: plan.version, blueprint_id: plan.blueprint_id })),
        analyze: targets.state.analyzeBodies,
        activeRolePuts: targets.state.activeRolePuts,
        links: targets.state.links,
      },
    },
  }));
  route("POST", "/__qa/reset", () => {
    Object.assign(state, { session: null, turns: [], ended: false, createBodies: [], answers: [], heartbeats: 0, unmocked: [], requests: [] });
    activeQuestions = QUESTIONS;
    state.idempotency.clear();
    state.clientTurns.clear();
    targets.reset();
    return { body: { ok: true } };
  });

  const apiServer = http.createServer(async (request, response) => {
    if (!guardRequest(request, response, apiServer)) return;
    if (request.method === "OPTIONS") return preflight(request, response);
    const url = new URL(request.url, "http://x");
    const pathname = url.pathname;
    const control = pathname.startsWith("/__qa/");
    if (!control) {
      const bearer = /^Bearer (.+)$/.exec(request.headers.authorization ?? "")?.[1];
      if (!verifyJwt(bearer)) {
        state.requests.push(`${request.method} ${pathname} 401`);
        return send(request, response, 401, { detail: "Invalid or expired access token" });
      }
    }
    const body = request.method === "GET" || request.method === "HEAD" ? null : await readBody(request);
    for (const entry of routes) {
      const match = entry.pattern.exec(pathname);
      if (entry.method !== request.method || !match) continue;
      const result = entry.handler({ match, body, url }) ?? err(500, "handler returned nothing");
      // A scenario may slow one answer down so loading states can be seen (never used by default).
      if (result.delayMs) await new Promise((resolve) => setTimeout(resolve, Math.min(result.delayMs, 5000)));
      const status = result.status ?? 200;
      if (!control) state.requests.push(`${request.method} ${pathname} ${status}`);
      return send(request, response, status, result.body);
    }
    state.unmocked.push(`API ${request.method} ${pathname}`);
    state.requests.push(`${request.method} ${pathname} 404`);
    return send(request, response, 404, { detail: "qa-mock: unmocked endpoint" });
  });

  const [boundAuth, boundApi] = await bindMockServers([authServer, apiServer], [authPort, apiPort]);
  authBase = supabaseUrl ?? `http://127.0.0.1:${boundAuth}`;
  const resolvedApi = apiUrl ?? `http://127.0.0.1:${boundApi}`;
  assertHermetic({ supabaseUrl: authBase, apiUrl: resolvedApi });

  return {
    authUrl: authBase,
    apiUrl: resolvedApi,
    authPort: boundAuth,
    apiPort: boundApi,
    email: QA_EMAIL,
    controlToken,
    state,
    close: () =>
      Promise.all([authServer, apiServer].map((server) => new Promise((resolve) => {
        server.closeAllConnections?.();
        server.close(resolve);
      }))),
  };
}
