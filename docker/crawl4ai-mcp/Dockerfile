FROM python:3.12-slim
RUN pip install --no-cache-dir "fastmcp==2.*" "httpx>=0.27"
COPY server.py /srv/server.py
ENV PYTHONUNBUFFERED=1 CRAWL4AI_URL=http://host.docker.internal:11235
ENTRYPOINT ["python", "/srv/server.py"]
