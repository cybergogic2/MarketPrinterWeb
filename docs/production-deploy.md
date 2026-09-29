# Production deployment

Target domain: `lk.magic-pvz.ru`

The production stack is:

- Caddy with automatic Let's Encrypt certificates and renewal
- Gunicorn/Django
- PostgreSQL

## First server setup

Install Docker Engine with the Compose plugin, open ports `80` and `443`, and clone the repository to:

```bash
/opt/MarketPrinterWeb
```

The file with server credentials, `.ht.auth`, must stay outside the repository. It is ignored by both the parent workspace and this repository.

Server access details are described locally in:

```bash
/Users/ivan/vibecoding/marat-ozon/.ht.auth
```

## Environment

Create the production environment file:

```bash
cp .env.example .env
```

Then edit `.env` and set real values for:

- `SECRET_KEY`
- `INTERNAL_API_KEY`
- `POSTGRES_PASSWORD`
- `LETSENCRYPT_EMAIL`

Generate a Django secret key with:

```bash
docker run --rm python:3.12-slim python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

For `lk.magic-pvz.ru`, keep:

```env
DOMAIN=lk.magic-pvz.ru
ALLOWED_HOSTS=lk.magic-pvz.ru
CSRF_TRUSTED_ORIGINS=https://lk.magic-pvz.ru
```

## Deploy

Run:

```bash
chmod +x scripts/deploy.sh scripts/backup.sh
./scripts/deploy.sh
```

The script validates the Compose file, builds the Django image, starts PostgreSQL, runs migrations, collects static files, and starts the full stack.

Useful checks:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f caddy
docker compose -f docker-compose.prod.yml logs -f web
curl -I https://lk.magic-pvz.ru/healthz/
```

## Autostart after reboot

Install the systemd unit:

```bash
cp deploy/marketprinter.service /etc/systemd/system/marketprinter.service
systemctl daemon-reload
systemctl enable marketprinter.service
systemctl start marketprinter.service
```

The unit runs:

```bash
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

Docker services also use `restart: unless-stopped`.

## TLS certificates

Caddy listens on `80` and `443`, issues the Let's Encrypt certificate for `DOMAIN`, stores it in the `caddy_data` Docker volume, and renews it automatically.

## Backups

Create a database and media backup:

```bash
./scripts/backup.sh
```

The files are written to `backups/`, which is gitignored. Copy backups off the server regularly.

Install the daily local backup timer:

```bash
cp deploy/marketprinter-backup.service /etc/systemd/system/marketprinter-backup.service
cp deploy/marketprinter-backup.timer /etc/systemd/system/marketprinter-backup.timer
systemctl daemon-reload
systemctl enable --now marketprinter-backup.timer
```

The timer runs at 03:15 server time and keeps local backup files for 14 days. This is not a replacement for off-server backups.

## Updating production

```bash
git pull
./scripts/deploy.sh
```

## Restore notes

Database restore example:

```bash
gzip -dc backups/postgres-YYYYmmdd-HHMMSS.sql.gz | docker compose -f docker-compose.prod.yml exec -T db sh -lc 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Media restore example:

```bash
tar -xzf backups/media-YYYYmmdd-HHMMSS.tar.gz -C media
```
