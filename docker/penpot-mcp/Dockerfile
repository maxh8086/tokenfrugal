FROM node:22-slim
RUN npm install -g @penpot/mcp@2.15.4 mcp-remote@0.1.38 pnpm@10 && npm cache clean --force
# @penpot/mcp ships as a pnpm monorepo: install and build once at image time.
WORKDIR /usr/local/lib/node_modules/@penpot/mcp
RUN pnpm -r install && pnpm run build
ENV PENPOT_MCP_SERVER_HOST=0.0.0.0 PENPOT_MCP_PLUGIN_SERVER_HOST=0.0.0.0
COPY entry.sh /entry.sh
RUN chmod +x /entry.sh
EXPOSE 4400 4401 4402
ENTRYPOINT ["/entry.sh"]
