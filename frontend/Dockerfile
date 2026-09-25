# VitalBand Frontend – Multi-stage Docker Image
# Stage 1: Build React/Vite app
# Stage 2: Serve with nginx:alpine

# ──────────────────────── Stage 1: Build ────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (layer cache)
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build production bundle
COPY . .
RUN npm run build

# ──────────────────────── Stage 2: Serve ────────────────────────
FROM nginx:alpine

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Use our custom nginx config that handles SPA routing and API proxying
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
