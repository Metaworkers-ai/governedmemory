# Multi-stage build producing Next.js's "standalone" output (see next.config.ts) --
# the final image needs neither the full node_modules nor the source tree.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Real values are supplied at container run time (see deploy/docker-compose.yml) --
# GOVERNEDMEMORY_API_KEY/_URL are read from process.env at request time in
# force-dynamic routes, never inlined into the build. These placeholders just
# satisfy next build's static analysis pass.
ENV GOVERNEDMEMORY_API_URL="http://api:8000"
ENV GOVERNEDMEMORY_API_KEY="build-placeholder-key"
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
