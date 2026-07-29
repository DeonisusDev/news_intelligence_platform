# Multi-stage: build the static SPA with Node, serve it with a plain nginx - no Node runtime
# needed (or wanted) in the final image, matching the "just render fetched JSON" scope of this
# frontend (see plan §8, Phase 6 - deliberately not Next.js/SSR).
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Baked in at build time (see vite's import.meta.env handling) - the compose service below
# passes this as a build arg so it's not hardcoded here.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
