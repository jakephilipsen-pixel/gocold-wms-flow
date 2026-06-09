# syntax=docker/dockerfile:1
#
# dim-capture-app backend (Express + Prisma). Build context is
# ./dim-capture-app/backend. Multi-stage: deps (prod node_modules + prisma
# engine) → builder (tsc) → runner (non-root, no dev deps).
#
# DATABASE_URL is NOT set here — the compose entrypoint assembles it at run
# time from the db_password Docker secret, so the DB password never lands in
# an image layer or in compose env. See docker-compose.yml + DEPLOY.md.

# ---- deps: production node_modules + generated prisma client -------------
FROM node:22-alpine AS deps
WORKDIR /app
# Prisma engines on Alpine need OpenSSL present, else they load the wrong
# libssl and the query engine fails to start.
RUN apk add --no-cache openssl
COPY package*.json ./
RUN npm ci --omit=dev
COPY prisma ./prisma
RUN npx prisma generate

# ---- builder: full deps + tsc build --------------------------------------
FROM node:22-alpine AS builder
WORKDIR /app
RUN apk add --no-cache openssl
COPY package*.json ./
RUN npm ci
COPY prisma ./prisma
RUN npx prisma generate
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# ---- runner: slim, non-root ----------------------------------------------
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# Runtime needs openssl too — the entrypoint runs `prisma migrate deploy`.
RUN apk add --no-cache openssl
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/prisma ./prisma
COPY package.json ./
# node:alpine ships an unprivileged `node` user (uid 1000); own the app dir
# so prisma + node run as non-root.
RUN chown -R node:node /app
USER node
EXPOSE 3005
# Fallback for standalone runs; compose overrides entrypoint to inject
# DATABASE_URL from the db_password secret before this runs.
CMD ["sh", "-c", "npx prisma migrate deploy && node dist/index.js"]
