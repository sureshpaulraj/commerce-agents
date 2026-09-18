// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/**
 * What a deployed web app needs and a loopback one does not: an HTTP Basic gate, and a
 * proxy that carries the browser's `/api` calls to the API from the server side.
 *
 * The browser cannot authenticate to a second origin with `fetch` — it never prompts,
 * and it attaches no credentials — so a deployed app serves its own `/api` path and
 * forwards from there, adding the API's credentials where the browser cannot see them.
 * That leaves one origin, one prompt, and no CORS. Build such an app with an empty
 * `NEXT_PUBLIC_API_URL` so `AgentApi` addresses its own origin.
 *
 * Both halves are inert until their variables are set, so a loopback demo is unchanged:
 *
 *   DEMO_BASIC_AUTH   `user:password`, demanded of the browser and offered to the API
 *   DEMO_API_ORIGIN   where the API answers, for example `https://host.example`
 *
 * Server-side only. Nothing here is importable from a client component.
 */

const REALM = 'Basic realm="Heartland demo", charset="UTF-8"';

/**
 * Read through a computed key. A bundler replaces `process.env.NAME` with the value it
 * saw when it built, which would freeze these into the image; a computed key is left to
 * run, so the container's own environment decides.
 */
function setting(name: string): string {
  const key = String(name);
  return (process.env as Record<string, string | undefined>)[key] ?? "";
}

/** Constant-time over the compared bytes, so a wrong header leaks no prefix length. */
function sameSecret(offered: string, expected: string): boolean {
  if (offered.length !== expected.length) return false;
  let difference = 0;
  for (let index = 0; index < offered.length; index += 1) {
    difference |= offered.charCodeAt(index) ^ expected.charCodeAt(index);
  }
  return difference === 0;
}

function credentialHeader(): string | null {
  const credentials = setting("DEMO_BASIC_AUTH").trim();
  return credentials ? `Basic ${btoa(credentials)}` : null;
}

/** The 401 to return when the request has not authenticated, or null when it has. */
export function basicAuthFailure(request: Request): Response | null {
  const expected = credentialHeader();
  if (!expected) return null;
  const offered = request.headers.get("authorization") ?? "";
  if (sameSecret(offered, expected)) return null;
  return new Response("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": REALM },
  });
}

/**
 * One browser call to `/api/...`, forwarded to the API with its credentials attached.
 * The response body is handed back unread, so a turn still streams.
 */
export async function proxyToApi(request: Request): Promise<Response> {
  const origin = setting("DEMO_API_ORIGIN").replace(/\/$/, "");
  if (!origin) {
    return new Response("DEMO_API_ORIGIN is not set.", { status: 502 });
  }
  const incoming = new URL(request.url);
  const headers = new Headers(request.headers);
  // The hop's own addressing and credentials replace the browser's.
  headers.delete("host");
  headers.delete("authorization");
  headers.delete("accept-encoding");
  const credentials = credentialHeader();
  if (credentials) headers.set("authorization", credentials);

  let upstream: Response;
  try {
    upstream = await fetch(`${origin}${incoming.pathname}${incoming.search}`, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return new Response("The API is unreachable.", { status: 502 });
  }

  const returned = new Headers(upstream.headers);
  // Hop-by-hop headers describe the hop that just ended, not this one.
  returned.delete("content-encoding");
  returned.delete("content-length");
  returned.delete("transfer-encoding");
  returned.delete("connection");
  return new Response(upstream.body, { status: upstream.status, headers: returned });
}
