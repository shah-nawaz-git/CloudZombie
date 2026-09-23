import { NextResponse, type NextRequest } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export function proxy(request: NextRequest) {
  const backendUrl = process.env.BACKEND_URL || DEFAULT_BACKEND_URL;
  const target = new URL(request.nextUrl.pathname + request.nextUrl.search, backendUrl);
  return NextResponse.rewrite(target);
}

export const config = { matcher: "/api/:path*" };
