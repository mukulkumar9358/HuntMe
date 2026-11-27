FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
# Next.js bakes rewrites into the build, so the backend address is a build-time argument.
ARG BACKEND_INTERNAL_URL=http://huntme-backend:8000
# WebSockets go straight from the browser to the API (Next rewrites can't proxy them), so this is the
# address the *browser* can reach, e.g. ws://localhost:8000 locally or wss://api.example.com in production.
ARG NEXT_PUBLIC_WS_URL=
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S huntme && adduser -S huntme -G huntme
COPY --from=build --chown=huntme:huntme /app/.next/standalone ./
COPY --from=build --chown=huntme:huntme /app/.next/static ./.next/static
COPY --from=build --chown=huntme:huntme /app/public ./public
USER huntme
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
