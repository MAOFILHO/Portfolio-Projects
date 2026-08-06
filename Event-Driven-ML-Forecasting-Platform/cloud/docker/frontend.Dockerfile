# Cloud image for the dashboard frontend. Unlike backend.Dockerfile, this
# one DOES bake the code in -- Vite's `npm run build` produces a static JS
# bundle that must exist by the time nginx starts, and VITE_API_BASE_URL is
# compiled into that bundle at build time (Vite env vars are not readable at
# container-runtime like a normal server env var, see
# frontend/src/api/client.ts), so it has to be supplied as a build ARG here,
# not a docker-compose `environment:` entry.
FROM node:20-slim AS build

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
# nginx.conf lives in cloud/docker/, outside this build's primary context
# (../../frontend, kept narrow so the build context doesn't include
# unrelated repo content). "nginxconf" is a named additional build context
# pointing at cloud/docker/ -- see docker-compose.cloud.yml's
# build.additional_contexts for the frontend service.
COPY --from=nginxconf nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
