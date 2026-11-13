# Build from the repo root:
#   docker build -f services/call-worker/Dockerfile -t agentsdr-call-worker .
# (Dokploy: build type Dockerfile, path services/call-worker/Dockerfile, context the repo root.)

# The recorder extension, built here from source: its dist/ is gitignored, so
# an image built from git (Dokploy) has no other copy. It needs only Bun, the
# extension, the call contracts it imports, and fflate. fflate is installed
# on its own: `bun add` beside the app's package.json would resolve all of the
# app's ~2,900 packages, and one missing from the registry fails the build.
# The app's package.json is copied only for its build:recorder script.
FROM oven/bun:1 AS recorder
WORKDIR /deps
RUN echo '{"private":true}' > package.json && bun add fflate@0.8.3
WORKDIR /app
COPY package.json ./
COPY extensions/whatsapp-recorder/ ./extensions/whatsapp-recorder/
COPY src/lib/calls/ ./src/lib/calls/
RUN cp -r /deps/node_modules ./node_modules && bun run build:recorder

FROM mcr.microsoft.com/playwright:v1.64.0-noble

RUN apt-get update \
 && apt-get install -y --no-install-recommends pulseaudio pulseaudio-utils xvfb unzip curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash

WORKDIR /app/services/call-worker
COPY services/call-worker/package.json services/call-worker/bun.lock* ./
RUN bun install --frozen-lockfile || bun install
# CloakBrowser's binary (~200 MB) baked into the image; it caches under ~/.cloakbrowser.
RUN npx cloakbrowser install

COPY services/call-worker/ ./
# The worker imports types and shapes from the app's call contracts.
COPY src/lib/calls/ /app/src/lib/calls/
COPY --from=recorder /app/extensions/whatsapp-recorder/dist/ /app/extensions/whatsapp-recorder/dist/

ENV EXTENSION_PATH=/app/extensions/whatsapp-recorder/dist \
    PROFILES_DIR=/data/profiles \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    LAUNCHERS=gologin_sdk \
    KEEP_OPEN=3 \
    CLOAK_TIMEZONE=Asia/Kolkata
# /data/profiles holds the cloak/local launchers' browser profiles (WhatsApp's
# login, CloakBrowser's fingerprint). GoLogin keeps its profiles in its own
# cloud; its Orbita browser (~400 MB) downloads to /root/.gologin on first use —
# mount a volume there too, or every restart downloads it again.
VOLUME ["/data", "/root/.gologin"]

ENTRYPOINT ["./docker-entrypoint.sh"]
