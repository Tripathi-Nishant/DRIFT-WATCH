# Small AWS deployment

This is the affordable single-server deployment for a small beta. It is not a
multi-region or high-availability architecture.

## Recommended instance

- One Ubuntu EC2 instance with 2 vCPU, 4 GB RAM, and 40–60 GB EBS.
- Security group allows SSH from your IP and HTTP/HTTPS from the internet.
- PostgreSQL port 5432 is bound to localhost only by Compose.
- Store the Compose `.env` file outside Git with restrictive permissions.

## Install and start

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
git clone https://github.com/Tripathi-Nishant/DRIFT-WATCH.git
cd DRIFT-WATCH
cp .env.example .env
nano .env
docker compose up -d --build
```

Use `docker compose ps`, `/healthz`, and `/readyz` as the deployment smoke
check. Do not open PostgreSQL to the public internet.

## Backups

Install the PostgreSQL client tools and run a daily backup to a private S3
bucket. Keep at least seven daily and four weekly backups. Do not put database
passwords or backup files in the Git repository.

```bash
mkdir -p backups
set -a; . ./.env; set +a
python tools/backup_postgres.py --output "backups/driftwatch-$(date +%Y%m%d).dump"
aws s3 cp backups/driftwatch-$(date +%Y%m%d).dump s3://YOUR_PRIVATE_BUCKET/driftwatch/
```

Add the command to a protected cron job only after testing it manually. Restore
one backup into a separate database at least monthly.

## HTTPS

For a real domain, install Caddy and use `Caddyfile.example`; Caddy obtains and
renews a trusted certificate automatically. Until a domain exists, keep the
server for development/testing only and do not send sensitive data over HTTP.

## Free Gemini mode

Set `GEMINI_API_KEY` and optionally `GEMINI_MODEL` in `.env`. DriftWatch uses
deterministic metrics when the key is absent. Keep Gemini calls low-volume and
never put the key in the dashboard or repository.
