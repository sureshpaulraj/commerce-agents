// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import { proxyToApi } from "web-shared/gateway";

/**
 * The API, served from this app's own origin so the browser needs no second set of
 * credentials; see ``web-shared/gateway``. Reached only when the app is built with an
 * empty ``NEXT_PUBLIC_API_URL``.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const GET = proxyToApi;
export const POST = proxyToApi;
export const PATCH = proxyToApi;
export const DELETE = proxyToApi;
