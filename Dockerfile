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
RUN pip install --no-cache-dir ".[server]"
COPY docker-entrypoint.sh /usr/local/bin/driftwatch-entrypoint
RUN chmod +x /usr/local/bin/driftwatch-entrypoint
ENV DRIFTWATCH_ENV=production
ENV DRIFTWATCH_DB=/data/driftwatch.db
ENV DRIFTWATCH_WEB_ROOT=/app/dashboard/dist
EXPOSE 8765
ENTRYPOINT ["driftwatch-entrypoint"]
CMD ["driftwatch", "serve", "--host", "0.0.0.0", "--port", "8765"]
