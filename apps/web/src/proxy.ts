import { createServerClient, type SetAllCookies } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

function redirectWithCookies(
  request: NextRequest,
  response: NextResponse,
  pathname: string,
  reason = "session_expired",
) {
  const url = request.nextUrl.clone();
  url.pathname = pathname;
  url.search = pathname === "/login" ? `?reason=${reason}` : "";
  const redirect = NextResponse.redirect(url);
  response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
  return redirect;
}

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const isAuthPage = request.nextUrl.pathname === "/login" || request.nextUrl.pathname === "/signup";

  if (!url || !key) {
    return isAuthPage ? response : redirectWithCookies(request, response, "/login", "configuration");
  }

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (cookiesToSet: Parameters<SetAllCookies>[0]) => {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // getClaims refreshes near-expiry tokens and verifies the resulting JWT.
  // Keep this immediately after client creation so refreshed cookies stay in sync.
  let isAuthenticated = false;
  try {
    const { data } = await supabase.auth.getClaims();
    isAuthenticated = Boolean(data?.claims.sub);
  } catch {
    // The auth service could not be reached. That is not the same as being signed out, so the
    // request goes on: each page checks the real session and only a genuine 401 sends anyone to sign in.
    return response;
  }
  if (!isAuthenticated && !isAuthPage) return redirectWithCookies(request, response, "/login");
  if (isAuthenticated && isAuthPage) return redirectWithCookies(request, response, "/dashboard");
  return response;
}

export const config = {
  matcher: [
    "/app/:path*",
    "/dashboard/:path*",
    "/practice/:path*",
    "/experience/:path*",
    "/stories/:path*",
    // The routes Practice and My Experience used to live at.
    "/diagnostics/:path*",
    "/evidence/:path*",
    "/roles/:path*",
    "/progress/:path*",
    "/help/:path*",
    "/settings/:path*",
    "/onboarding",
    "/sessions/:path*",
    "/login",
    "/signup",
  ],
};
