// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import { basicAuthFailure } from "web-shared/gateway";

/**
 * Next runs this before every matched request. It holds the HTTP Basic gate, which is
 * inert until ``DEMO_BASIC_AUTH`` is set; see ``web-shared/gateway``.
 */
export function proxy(request: Request) {
  return basicAuthFailure(request) ?? undefined;
}

export const config = {
  // Next's own build output carries nothing the gate protects.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
