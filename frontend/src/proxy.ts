import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Edge gate: redirect to /login before a protected page renders if there's no
// session cookie, so a logged-out user never sees a flash of app chrome. This is
// an optimistic presence check (the API still validates the JWT); AuthGuard stays
// as the client-side backstop. Public routes (/, marketing, /login, /register,
// /research, password reset) are intentionally not matched — except when the
// request comes from app.penkeep.io, which always routes into the app.
export function proxy(request: NextRequest) {
  const hostname = request.headers.get("host") ?? "";
  const isAppSubdomain = hostname.startsWith("app.");

  // app.penkeep.io/ → /dashboard (auth gate below will redirect to /login if needed)
  if (request.nextUrl.pathname === "/") {
    if (isAppSubdomain) {
      const url = request.nextUrl.clone();
      url.pathname = "/dashboard";
      return NextResponse.redirect(url);
    }
    // Marketing homepage — always public
    return NextResponse.next();
  }

  const hasSession =
    request.cookies.has("access_token") || request.cookies.has("refresh_token");
  if (hasSession) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.search = `?from=${encodeURIComponent(request.nextUrl.pathname)}`;
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/",
    "/dashboard",
    "/dashboard/:path*",
    "/connect",
    "/connect/:path*",
    "/onboarding",
    "/onboarding/:path*",
    "/digests",
    "/digests/:path*",
    "/settings",
    "/settings/:path*",
  ],
};
