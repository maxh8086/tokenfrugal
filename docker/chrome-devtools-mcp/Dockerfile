FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-liberation \
 && apt-get clean \
 && npm install -g chrome-devtools-mcp@1.10.1 && npm cache clean --force
ENV CHROME_PATH=/usr/bin/chromium
# Headless, throwaway profile, no sandbox (container is the sandbox). Override with extra args if needed.
ENTRYPOINT ["chrome-devtools-mcp", "--headless", "--isolated", "--executablePath=/usr/bin/chromium", "--chromeArg=--no-sandbox", "--chromeArg=--disable-dev-shm-usage"]
