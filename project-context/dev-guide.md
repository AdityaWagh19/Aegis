# Developer Guide — Aegis

> **Note:** This document is the basis for `README.md` at submission time.
> Keep it current throughout the 13-day build. Any new dependency, env var, or workflow step must be added here immediately.

---

## Technology Stack

### Backend

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.12+ |
| Web framework | FastAPI (async) | Latest |
| LLM client | Groq Python SDK | Latest |
| Razorpay client | `razorpay` Python SDK | Latest |
| ORM | SQLAlchemy 2.0 (async) | 2.x |
| Validation | Pydantic | v2 |
| Config loader | PyYAML | Latest |
| Synthetic data | `faker` (`en_IN` locale) | Latest |
| Testing | pytest, pytest-asyncio | Latest |

### Database

| Option | Use Case |
|---|---|
| SQLite | Fast local development, single-file, no setup |
| PostgreSQL 16 | Production-realistic; required for `REVOKE UPDATE, DELETE` on `audit_log` |

> Use SQLite during development (Days 1–10). Switch to PostgreSQL for the EC2 deployment if time allows. The audit-log append-only constraint must be enforced in application code for SQLite.

### Frontend

| Component | Technology |
|---|---|
| Framework | React 18 with TypeScript (preferred) |
| Charts | Recharts or Chart.js |
| File upload | react-dropzone |
| Alternative | Streamlit (faster to build if solo; use if React takes more than 2 days) |

### Infrastructure

| Component | Technology |
|---|---|
| Cloud | AWS EC2 (t3.small minimum, t3.medium recommended) |
| OS | Ubuntu 22.04 LTS |
| Reverse proxy | Nginx |
| SSL | Let's Encrypt via certbot |
| Process manager | Docker Compose |
| CI/CD | GitHub Actions |

---

## Groq Model Selection

Groq is used instead of Anthropic. Free API tier, extremely low inference latency, OpenAI-compatible interface.

| Use Case | Model | Reason |
|---|---|---|
| Tier-2 primary reasoning | `llama-3.3-70b-versatile` | Best accuracy for ambiguous composite cases; most reliable structured output; best Hinglish quality |
| Tier-2 high-volume (batch > 100) | `llama-3.1-8b-instant` | ~5x faster than 70B; use when speed matters more than marginal accuracy |
| Hinglish message drafting | `llama-3.3-70b-versatile` | Better cultural fluency and code-switching quality |
| Fallback if rate-limited | `mixtral-8x7b-32768` | Solid function calling, 32k context window |

**Rate limits (free tier):**
- `llama-3.3-70b-versatile`: ~30 requests/minute, ~14,400/day
- `llama-3.1-8b-instant`: ~60 requests/minute
- A demo batch of 50–200 records produces 12–70 Tier-2 calls — well within limits.

**Temperature:**
- `temperature=0.2` for Hinglish message drafting (slight variety)
- `temperature=0` for action selection if using a two-step prompt

---

## Local Setup

### Prerequisites

- Python 3.12+
- Node.js 20+ (for React dashboard)
- Git

### 1. Clone and install dependencies

```bash
git clone https://github.com/AdityaWagh19/Aegis.git
cd Aegis
pip install -r requirements.txt
```

### 2. Create `.env` from template

```bash
cp .env.example .env
# Edit .env and fill in all required values (see Environment Variables section below)
```

### 3. Run the backend

```bash
# SQLite (development default)
uvicorn api.main:app --reload --port 8000
```

### 4. Generate synthetic data and held-out set

```bash
# Run BEFORE writing any rules — held-out set must be reserved first
python -m synthetic.generator --count 500 --output data/synthetic.csv --held-out-pct 0.2
```

### 5. Run tests

```bash
# Unit tests (no external API calls)
pytest tests/unit/ -v

# Compliance gate tests specifically
pytest tests/unit/test_compliance_gate.py -v --tb=short

# Integration tests (requires GROQ_API_KEY)
pytest tests/integration/ -v
```

### 6. Run the React dashboard (development)

```bash
cd dashboard
npm install
npm run dev
# Dashboard available at http://localhost:3000
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values. Never commit `.env`.

### Groq API

```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL_TIER2=llama-3.3-70b-versatile
GROQ_MODEL_TIER2_FAST=llama-3.1-8b-instant
GROQ_MODEL_FALLBACK=mixtral-8x7b-32768
```

### Razorpay (Test Mode ONLY)

```bash
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> Register the webhook in the Razorpay dashboard:
> `https://aegis.yourdomain.com/webhooks/razorpay`
> Events to subscribe: `payment.failed`, `subscription.pending`, `subscription.charged`, `subscription.activated`

### Database

```bash
DB_PASSWORD=your_strong_random_password_here
DATABASE_URL=postgresql://aegis:${DB_PASSWORD}@db:5432/aegis
# For local SQLite development:
# DATABASE_URL=sqlite:///./aegis.db
```

### Application Security

```bash
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_64_char_hex_secret_here
```

### CORS and Hosting

```bash
ALLOWED_ORIGINS=https://aegis.yourdomain.com,http://localhost:3000
APP_HOST=aegis.yourdomain.com
```

### Compliance (Defaults — real values live in `compliance_config.yaml`)

```bash
AFA_THRESHOLD_GENERAL=15000
AFA_THRESHOLD_SIP_INSURANCE=100000
```

### Application Behaviour

```bash
ENVIRONMENT=development      # development | production
LOG_LEVEL=DEBUG              # DEBUG | INFO | WARNING | ERROR
```

---

## Code Organisation — Key Rules

| Rule | Rationale |
|---|---|
| `core/tier1_engine.py` must have zero imports from any LLM module | Enforces the architectural constraint that Tier-1 uses no LLM |
| `core/compliance_gate.py` must have zero imports from `core/tier1_engine.py` or `core/tier2_agent.py` | Gate must be structurally independent |
| All Razorpay calls must use test-mode key IDs (`rzp_test_*`) | Never live keys during development or testing |
| `data/held_out*` files must be generated before any rule-writing begins | Prevents contamination of the evaluation set |
| All compliance thresholds come from `compliance_config.yaml`, not hardcoded | Config-driven thresholds are auditable and changeable without a code deploy |

---

## Engineering Constraints (Hard Rules)

| Timeline | 13 build days | MVP delivery |
| Failure categories modeled | Exactly 6 (the taxonomy) | Depth over breadth |
| LLM on compliance decisions | Not permitted | Compliance gate is unconditional deterministic code |
| Tier-2 (LLM) volume | Must not exceed ~30% of the batch | If more, Tier-1 rule engine needs improvement |
| Bandit/RL optimizer | Not in MVP | No real convergence on synthetic data |
| Real WhatsApp/telephony | Not in MVP | Mock stub is expected and sufficient |
| Real customer PII | Not permitted | Synthetic data only |
| Live money | Not permitted | Razorpay test-mode only |

---

## Running Tests Before Commit

Run this sequence before every push to `main`:

```bash
# 1. Unit tests (fast, no external calls)
pytest tests/unit/ -v

# 2. Compliance gate must never fail
pytest tests/unit/test_compliance_gate.py -v --tb=long

# 3. Check Tier-2 output schema validation
pytest tests/unit/test_tier2_schema.py -v
```

The CI pipeline (GitHub Actions) runs steps 1 and 2 on every push. If either fails, the deploy step does not run.

---

*Source: Master_Aegis.md §14, §18, §24 Steps 4-5, §25 | Last updated: 2026-08-23*
