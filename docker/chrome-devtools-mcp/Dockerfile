# Build the server from the pinned source (the build context is the clone at docker/pins.yaml sha).
FROM node:22-slim AS build
WORKDIR /src
COPY . .
RUN mkdir -p /out && npm ci --ignore-scripts && npm run build && npm pack --pack-destination /out

FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-liberation \
 && apt-get clean
COPY --from=build /out/*.tgz /tmp/
RUN npm install -g /tmp/*.tgz && rm -f /tmp/*.tgz && npm cache clean --force
ENV CHROME_PATH=/usr/bin/chromium
# Headless, throwaway profile, no sandbox (container is the sandbox). Override with extra args if needed.
ENTRYPOINT ["chrome-devtools-mcp", "--headless", "--isolated", "--executablePath=/usr/bin/chromium", "--chromeArg=--no-sandbox", "--chromeArg=--disable-dev-shm-usage"]
