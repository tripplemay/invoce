# syntax=docker/dockerfile:1

# ---- Builder stage ----
FROM node:20-alpine AS builder
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

# 可选 npm 镜像源：本地中国网络构建时传入 npmmirror；GitHub CI 不传 → 用官方源
ARG NPM_REGISTRY=""

# Install dependencies (respects .npmrc: legacy-peer-deps for React 19 RC)
COPY package.json ./
COPY .npmrc ./
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi && npm install

# Copy source and build
COPY . .
# Next 的 NEXT_PUBLIC_* 是构建期变量，必须在 build 前注入生产 API 地址
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

# ---- Runner stage ----
FROM node:20-alpine AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

# Copy the built app and its dependencies from the builder
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/.npmrc ./.npmrc
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./next.config.js

EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000"]
