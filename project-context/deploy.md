# Deployment Guide — Aegis

> **Status:** Reference | Read on Day 1 for initial EC2 setup. Revisit on Day 12 for final production deploy.

---

## Infrastructure Overview

```
[GitHub Repo: Aegis]
         |
   push to main branch
         |
   GitHub Actions workflow
   (test -> build -> rsync -> deploy)
         |
[AWS EC2 Instance (Aegis)]
  Ubuntu 22.04 LTS, t3.medium
  Elastic IP assigned
         |
  Nginx (:80/:443)
    |-- /api      --> FastAPI (:8000)
    |-- /webhooks --> FastAPI (:8000)
    `-- /         --> React build (static) or Streamlit (:8501)
         |
  PostgreSQL / SQLite (internal only)
  Docker Compose manages all services
```

> Aegis runs on its own dedicated EC2 instance — completely separate from any other projects.

---

## Step 1 — EC2 Instance Setup (One-Time)

```bash
# 1. Launch EC2: Ubuntu 22.04 LTS, t3.small minimum (t3.medium recommended)
# 2. Security Group inbound rules:
#    - Port 22  (SSH)   — your IP only
#    - Port 80  (HTTP)  — 0.0.0.0/0
#    - Port 443 (HTTPS) — 0.0.0.0/0
# 3. Assign an Elastic IP to the instance

# SSH into the instance
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Install Docker + Docker Compose + Nginx + certbot
sudo apt update && sudo apt install -y \
  docker.io docker-compose-plugin git nginx certbot python3-certbot-nginx

sudo usermod -aG docker ubuntu
newgrp docker

# Create app directory
mkdir -p /home/ubuntu/Aegis
```

---

## Step 2 — Nginx Configuration

Create `/etc/nginx/sites-available/aegis`:

```nginx
server {
    listen 80;
    server_name aegis.yourdomain.com;   # Replace with your domain or EC2 Elastic IP

    # API — FastAPI backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Razorpay webhooks
    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # React dashboard — serve static build
    # If using Streamlit instead:
    # location / { proxy_pass http://127.0.0.1:8501; }
    location / {
        root /home/ubuntu/Aegis/dashboard/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
# Enable and test
sudo ln -s /etc/nginx/sites-available/aegis /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL via Let's Encrypt
sudo certbot --nginx -d aegis.yourdomain.com
```

---

## Step 3 — Docker Compose

`docker-compose.yml` is committed to the repo (no secrets):

```yaml
version: '3.8'
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env           # .env lives on EC2, never in repo
    volumes:
      - ./compliance_config.yaml:/app/compliance_config.yaml
      - ./data:/app/data     # Synthetic data + held-out fixtures
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: aegis
      POSTGRES_USER: aegis
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aegis"]
      interval: 10s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --save 60 1
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5
    restart: unless-stopped

  worker:
    build: .
    command: python -m arq workers.mandate_worker.WorkerSettings
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
```

> **Note:** The `redis` and `worker` services are added in Phase 9. Phases 1–8 (MVP) only need `api` and `db`. You can run the Phase 1–8 system by commenting out `redis` and `worker` with `docker compose --profile mvp up` once profiles are set, or by simply running `docker compose up api db`.

---

## Step 4 — `.env` on EC2 (Never Commit This)

Create this file at `/home/ubuntu/Aegis/.env` directly on the EC2 instance:

```bash
# ============================================================
# Aegis — Environment Configuration
# DO NOT commit this file. It is excluded by .gitignore.
# ============================================================

# Groq API (LLM — Tier-2 Reasoning and Hinglish Drafting)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL_TIER2=llama-3.3-70b-versatile
GROQ_MODEL_TIER2_FAST=llama-3.1-8b-instant
GROQ_MODEL_FALLBACK=mixtral-8x7b-32768

# Razorpay (Test Mode ONLY)
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# PostgreSQL Database
DB_PASSWORD=your_strong_random_password_here
DATABASE_URL=postgresql://aegis:${DB_PASSWORD}@db:5432/aegis

# Application Security
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_64_char_hex_secret_here

# CORS and Hosting
ALLOWED_ORIGINS=https://aegis.yourdomain.com,http://localhost:3000
APP_HOST=aegis.yourdomain.com

# Compliance (real values live in compliance_config.yaml)
AFA_THRESHOLD_GENERAL=15000
AFA_THRESHOLD_SIP_INSURANCE=100000

# Application Behaviour
ENVIRONMENT=production
LOG_LEVEL=INFO

# ============================================================
# Phase 9 — Production Hardening (add these when implementing Phase 9)
# ============================================================

# Redis (ARQ job queue + Tier-2 rate limiter)
REDIS_URL=redis://redis:6379/0

# Fernet master key for encrypting tenant Razorpay credentials at rest
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
AEGIS_MASTER_ENCRYPTION_KEY=your_fernet_key_here

# Prometheus metrics
PROMETHEUS_ENABLED=1
```

---

## Step 5 — `.env.example` (Committed to Repo)

```bash
# .env.example — committed to repo as a template
# Copy to .env and fill in real values on your EC2 instance

GROQ_API_KEY=
GROQ_MODEL_TIER2=llama-3.3-70b-versatile
GROQ_MODEL_TIER2_FAST=llama-3.1-8b-instant
GROQ_MODEL_FALLBACK=mixtral-8x7b-32768

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

DB_PASSWORD=
DATABASE_URL=postgresql://aegis:changeme@db:5432/aegis

SECRET_KEY=
ALLOWED_ORIGINS=http://localhost:3000
APP_HOST=localhost

AFA_THRESHOLD_GENERAL=15000
AFA_THRESHOLD_SIP_INSURANCE=100000

ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

---

## Step 6 — GitHub Actions CI/CD Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Aegis to EC2

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v
        env:
          GROQ_API_KEY: test_key_not_used_in_unit_tests
          DATABASE_URL: sqlite:///./test.db
          SECRET_KEY: test_secret_key_32_chars_minimum_here
      - name: Run compliance gate tests
        run: pytest tests/unit/test_compliance_gate.py -v --tb=short
        env:
          GROQ_API_KEY: test_key_not_used_in_unit_tests
          DATABASE_URL: sqlite:///./test.db
          SECRET_KEY: test_secret_key_32_chars_minimum_here
      - name: Run Phase 9 auth and rate limiter tests (if implemented)
        run: |
          if [ -f tests/unit/test_auth_middleware.py ]; then
            pytest tests/unit/test_auth_middleware.py tests/unit/test_rate_limiter.py -v --tb=short
          fi
        env:
          GROQ_API_KEY: test_key_not_used_in_unit_tests
          DATABASE_URL: sqlite:///./test.db
          SECRET_KEY: test_secret_key_32_chars_minimum_here
          REDIS_URL: redis://localhost:6379/0
          AEGIS_MASTER_ENCRYPTION_KEY: dGVzdGtleWZvcmNpZW52aXJvbm1lbnQ=

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Build React dashboard
        working-directory: ./dashboard
        run: |
          npm ci
          npm run build

      - name: Copy files to EC2 via rsync
        uses: burnett01/rsync-deployments@7.0.1
        with:
          switches: >
            -avzr --delete
            --exclude='.env'
            --exclude='node_modules'
            --exclude='__pycache__'
            --exclude='data/held_out*'
          path: ./
          remote_path: /home/ubuntu/Aegis
          remote_host: ${{ secrets.EC2_HOST }}
          remote_user: ${{ secrets.EC2_USERNAME }}
          remote_key: ${{ secrets.EC2_SSH_PRIVATE_KEY }}

      - name: Deploy on EC2
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USERNAME }}
          key: ${{ secrets.EC2_SSH_PRIVATE_KEY }}
          script: |
            cd /home/ubuntu/Aegis
            docker compose run --rm api alembic upgrade head
            docker compose up --build -d
            sudo systemctl reload nginx
            echo "Aegis deployed successfully"
```

---

## GitHub Repository Secrets

Configure in GitHub Settings > Secrets > Actions:

| Secret Name | Value |
|---|---|
| `EC2_HOST` | Aegis's EC2 Elastic IP or domain |
| `EC2_SSH_PRIVATE_KEY` | Full contents of the EC2 `.pem` key file |
| `EC2_USERNAME` | `ubuntu` (Ubuntu AMI) |

> All application secrets (`GROQ_API_KEY`, `RAZORPAY_KEY_SECRET`, etc.) are stored in `.env` **directly on the EC2 instance**. The rsync step uses `--exclude='.env'` so the live `.env` is never overwritten by CI/CD.

> The rsync step also excludes `data/held_out*` to protect the held-out evaluation set from being overwritten by any generated data during development.

---

## First-Time Deployment Checklist

- [ ] EC2 instance launched (Ubuntu 22.04, t3.small+), Elastic IP assigned
- [ ] Security groups open: ports 22, 80, 443
- [ ] Docker + Docker Compose + Nginx + certbot installed on EC2
- [ ] `/home/ubuntu/Aegis/.env` created with all real values
- [ ] `compliance_config.yaml` reviewed and committed to repo
- [ ] Nginx config created and enabled at `/etc/nginx/sites-available/aegis`
- [ ] SSL certificate obtained via certbot
- [ ] Razorpay webhook URL registered: `https://aegis.yourdomain.com/webhooks/razorpay`
- [ ] Razorpay: at least one test Plan + Subscription created for the charge simulator
- [ ] GitHub repo secrets set: `EC2_HOST`, `EC2_SSH_PRIVATE_KEY`, `EC2_USERNAME`
- [ ] Held-out set pre-generated and committed as `data/synthetic_held_out.csv` before any rule-writing begins
- [ ] First manual deploy: `docker compose up --build -d` on EC2
- [ ] Push to `main` branch and verify GitHub Actions workflow passes

---

## Re-Deployment Procedure

After initial setup, deployment is fully automated:

1. Push code to `main` branch
2. GitHub Actions runs unit tests and compliance gate tests
3. If tests pass, rsync deploys to EC2 and restarts Docker Compose
4. Nginx is reloaded

If tests fail, the deploy step does not run. Fix the failure before merging.

---

## Troubleshooting

| Issue | Resolution |
|---|---|
| API returns 502 Bad Gateway | FastAPI container is not running. Run `docker compose ps` and check logs: `docker compose logs api` |
| Compliance gate test fails in CI | Fix the gate before merging. The test suite is non-negotiable. |
| Groq rate limit hit during demo | Switch `GROQ_MODEL_TIER2` to `llama-3.1-8b-instant` (60 req/min vs 30 req/min) |
| Razorpay webhook not received | Verify the webhook URL in Razorpay dashboard matches the Nginx route exactly |
| `data/held_out*` overwritten | Restore from git history. The rsync exclusion prevents this in CI; check if it was manually overwritten. |

---

*Source: Master_Aegis.md §18, §24 | Last updated: 2026-08-23*
