# Ironpass

A modular compliance proxy that sits between AI agents and LLMs/external APIs. Intercepts every agent request, detects sensitive data, applies ruleset-defined actions (tokenize, mask, block, pseudonymize), logs everything immutably, and returns sanitized content.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Fill in required values in .env

# 2. Start services
make up

# 3. Verify
curl http://localhost:8000/health
```

## Architecture

See [Architecture.md](./Architecture.md) for the full system design.

## Tech Stack

| Component | Technology |
|---|---|
| API / Proxy | Python 3.11 + FastAPI |
| Detection | Regex + Luhn + spaCy NER |
| Database | PostgreSQL 15 + SQLAlchemy |
| Encryption | AES-256-GCM |
| Cache | Redis 7 |
| Dashboard | React 18 + TailwindCSS |
| Containerization | Docker + Docker Compose |

## Development

```bash
make up          # Start all services
make down        # Stop all services
make logs        # Follow logs
make test        # Run all tests
make db-shell    # PostgreSQL shell
make redis-shell # Redis CLI
```

## License

Proprietary. All rights reserved.
