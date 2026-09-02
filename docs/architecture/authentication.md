# Authentication and user identity

This milestone uses Supabase Auth as Mirror's sole identity provider. It adds identity and session handling only; onboarding and authorization by institutional role remain out of scope.

## Frontend flow

The Next.js application exposes separate `/login` and `/signup` routes. Email/password operations use the browser-safe Supabase URL and anonymous/publishable key. Google OAuth is shown only when `NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED=true`; the Supabase project must also have the Google provider and the `/auth/callback` redirect URL configured.

Supabase SSR stores and refreshes the session in cookies. `src/proxy.ts` refreshes authentication state and guards `/app` and the existing `/sessions/*` candidate routes. An unauthenticated or expired session is redirected to `/login`; an authenticated visitor to `/login` or `/signup` is redirected to `/app`. The callback exchanges the OAuth authorization code for a cookie session and rejects unsafe external `next` destinations.

The browser sends the current Supabase access token to the FastAPI service in an `Authorization: Bearer` header. It never sends a `user_id` as proof of identity. Authentication errors shown by the UI are deliberately mapped to stable, user-safe messages rather than provider or backend exception text. Missing configuration fails closed.

## Backend token verification

`get_current_user()` is the reusable FastAPI authentication dependency. It parses the bearer credential and sends the access token to Supabase Auth's authoritative `/auth/v1/user` endpoint. Supabase verifies the JWT signature, expiry and validity before returning the authenticated user. Mirror then validates and converts the returned subject to a UUID and treats that result as the trusted identity.

Missing, malformed, invalid and expired credentials return `401` with a Bearer challenge. Supabase connectivity failures return a generic `503`; raw upstream responses are not exposed. The compatibility `current_user_id()` dependency derives its UUID from `get_current_user()` so existing owner-scoped session routes use the same boundary.

`GET /api/v1/me` reconciles the trusted Auth subject with `public.profiles` and returns `id`, `full_name`, and `email`. `PATCH /api/v1/me` accepts only `full_name`; Pydantic rejects extra fields, so callers cannot submit or modify an ID. Both operations scope repository queries to the verified subject.

## Supabase responsibility

Supabase Auth owns passwords, password hashing, email confirmation, OAuth exchange, access/refresh token creation, token expiry, and session refresh. Mirror never stores a password.

The authentication migration keeps `public.profiles.id` tied to `auth.users.id`. Its trigger creates a profile for new email/password and OAuth users and reconciles email or initially missing provider name metadata. The API also reconciles on the first `/me` request to recover safely if a historical account predates the trigger.

The browser receives only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. `SUPABASE_SERVICE_ROLE_KEY` is server-only and is used by the backend profile repository; it must never be added to a `NEXT_PUBLIC_*` variable, browser bundle, log, or client response.

## RLS responsibility

RLS is the database backstop. `profiles_select_own` and `profiles_update_own` compare `profiles.id` to `auth.uid()`. Authenticated database clients receive column-level update permission for `full_name` only; email and ID reconciliation remains a trusted backend operation. Existing session and turn policies continue to derive ownership through `auth.uid()`, so one user cannot select another user's profile, session, or transcript.

The service role bypasses RLS by design. Backend repositories must therefore include the verified user ID in every profile/session filter and must never accept a payload user ID as the owner selector.

