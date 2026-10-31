FROM node:22-slim AS dashboard-build
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY web ./web
COPY migrations ./migrations
COPY tools ./tools
COPY --from=dashboard-build /app/dashboard/dist ./dashboard/dist
# Apply the latest security updates available in the base distribution before
# installing the application. Trivy still reports vulnerabilities that Debian
# has not fixed yet, which CI handles with ignore-unfixed.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir ".[server]"
COPY docker-entrypoint.sh /usr/local/bin/driftwatch-entrypoint
RUN chmod +x /usr/local/bin/driftwatch-entrypoint \
    && addgroup --system driftwatch \
    && adduser --system --ingroup driftwatch driftwatch \
    && mkdir -p /data \
    && chown -R driftwatch:driftwatch /app /data
USER driftwatch
ENV DRIFTWATCH_ENV=production
ENV DRIFTWATCH_DB=/data/driftwatch.db
ENV DRIFTWATCH_WEB_ROOT=/app/dashboard/dist
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=3)"
ENTRYPOINT ["driftwatch-entrypoint"]
CMD ["driftwatch", "serve", "--host", "0.0.0.0", "--port", "8765"]
