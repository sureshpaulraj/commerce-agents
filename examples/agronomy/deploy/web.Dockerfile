# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
#
# Either agronomy web app, for Azure Container Apps. The app is one workspace of the
# `examples/` npm workspace and depends on `web-shared` through a relative `file:`
# specifier, so the build context is `examples/` and the app keeps its path inside the
# image. Build from the repository root:
#   az acr build -r <registry> -t agronomy-storefront:latest \
#     -f examples/agronomy/deploy/web.Dockerfile \
#     --build-arg APP=storefront-web \
#     --build-arg NEXT_PUBLIC_API_URL=https://<api-fqdn> examples
#
# The install is `npm ci`, so the tree is exactly what `package-lock.json` records and
# no version range is resolved again at build time: the image carries the audited set.
# The direct dependencies are nine first-party packages — next, react, react-dom,
# typescript, tailwindcss, @tailwindcss/postcss and the three @types — plus the local
# `web-shared`. On a network that requires an approved mirror rather than the public
# registry, pass --build-arg NPM_REGISTRY=<feed url>; a mirror that carries the
# mainstream registry carries all of it.
#
# Optional and development dependencies are pruned after the build, so the shipped image
# carries neither the LGPL `@img/sharp-libvips-*` binaries nor the MPL `lightningcss*`
# ones. Both are needed to produce the build and neither is needed to serve it: sharp is
# Next's image-optimisation backend and nothing here imports `next/image`, and
# lightningcss is Tailwind's build-time CSS transform. What remains at run time is next,
# react and react-dom.
#
# NEXT_PUBLIC_API_URL is inlined by `next build`, so the API's address is a build
# argument rather than a runtime variable: the browser, not the server, calls the API.

FROM node:22-slim

ARG APP=storefront-web
ARG NEXT_PUBLIC_API_URL
ARG NPM_REGISTRY=https://registry.npmjs.org
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /src

# The whole workspace, because `npm ci` refuses a lockfile that does not describe the
# same set of workspaces it was written from.
COPY . .

RUN npm config set registry "$NPM_REGISTRY" \
    && npm ci --no-audit --no-fund \
    && npm run build --workspace "agronomy/$APP" \
    && npm prune --omit=dev --omit=optional \
    && find node_modules -mindepth 1 -maxdepth 1 -type d -empty -delete

ENV NODE_ENV=production
WORKDIR /src/agronomy/$APP
EXPOSE 3000
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
