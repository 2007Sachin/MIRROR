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

  // getUser performs an authenticated server round-trip and refreshes stale cookies.
  let user = null;
  try {
    ({ data: { user } } = await supabase.auth.getUser());
  } catch {
    return isAuthPage ? response : redirectWithCookies(request, response, "/login", "network");
  }
  if (!user && !isAuthPage) return redirectWithCookies(request, response, "/login");
  if (user && isAuthPage) return redirectWithCookies(request, response, "/app");
  return response;
}

export const config = {
  matcher: ["/app/:path*", "/onboarding", "/sessions/:path*", "/login", "/signup"],
};

