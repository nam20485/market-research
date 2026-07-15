# syntax=docker/dockerfile:1
#
# Frontend image for the market-research Vite/React app.
#
# Two usable targets:
#   - `dev`  (default): Node + pnpm running the Vite dev server with HMR,
#             proxying /api and /healthz to the backend service. Used by
#             `docker-compose.yml`'s default `frontend` service.
#   - `prod`: builds the static `pnpm build` output (frontend/dist — the
#             same artifact later deployed to Cloudflare Pages) and serves
#             it with nginx. Used by the optional `frontend-prod` compose
#             service (profile "prod") as a "prod-like" local preview; it is
#             NOT how the real Cloudflare Pages deploy works (that's handled
#             by cloudflare/pages-action in .github/workflows/cloudflare_deploy.yml).

FROM node:24-slim AS base
WORKDIR /app
RUN corepack enable

FROM base AS dev
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
EXPOSE 5173
# NB: no `--` separator before `--host` — pnpm forwards it literally to vite's
# argv, which then treats `--` as an "end of flags" marker and never binds to
# 0.0.0.0, leaving the dev server reachable only from inside the container.
CMD ["pnpm", "dev", "--host"]

FROM base AS build
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
