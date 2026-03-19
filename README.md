# Ironpass

Ironpass is a security and compliance layer for AI agents. It sits between an agent and an LLM or external API, detects sensitive data before it leaves your system, applies policy-driven actions, and forwards only sanitized content.

## Overview

LLM-powered products often send raw prompts, customer records, payment details, or health-related text straight to upstream APIs. Ironpass is designed to reduce that risk by acting as a control point for outbound agent traffic.

In the current repo, Ironpass provides:

- a FastAPI-based compliance proxy
- detection pipelines for sensitive data
- policy actions such as tokenize, mask, block, and pseudonymize
- YAML-defined rulesets for regulated data handling
- audit logging and token vault foundations
- Python and Node SDKs for integration
- a lightweight dashboard shell for visibility into health, violations, audit logs, and rulesets

## Core Use Case

If an agent tries to send PII, PCI, HIPAA-related content, or other sensitive text to an LLM, Ironpass can:

1. inspect the outgoing payload
2. detect regulated or sensitive data
3. apply the configured action for each ruleset
4. forward sanitized content upstream
5. record an audit trail for what happened

## How It Works

Ironpass currently supports two main integration patterns:

### 1. Transparent OpenAI-Compatible Proxy

The primary path is a drop-in proxy endpoint:

- `POST /openai/v1/chat/completions`

This allows an agent to point its OpenAI client at Ironpass first, while Ironpass handles interception, sanitization, forwarding, and response de-tokenization.

### 2. Explicit Scan Endpoint

For agents that want direct control, Ironpass also exposes:

- `POST /proxy/scan`

This returns sanitized content and compliance metadata without forcing a forward to an upstream model.

## Detection and Enforcement Model

The current engine combines multiple detection layers:

- regex-based pattern matching for fast deterministic detection
- Luhn validation for payment-card refinement
- spaCy NER for context-aware entity detection

Actions are driven by YAML rulesets and currently include:

- `tokenize`
- `mask`
- `block`
- `pseudonymize`

Built-in ruleset definitions in the repo include:

- PCI-DSS
- HIPAA
- GDPR
- SOC 2

## Repository Structure

```text
engine/                FastAPI proxy, detection, actions, vault, audit, rulesets
dashboard/             Backend and frontend dashboard surfaces
sdk/python/            Python SDK
sdk/nodejs/            Node/TypeScript SDK
tests/                 Verification scripts and test scaffolding
Architecture.md        Detailed system design
docker-compose.yml     Local development stack
```

## Tech Stack

- Python 3.11
- FastAPI
- PostgreSQL
- Redis
- SQLAlchemy
- spaCy
- React
- Tailwind CSS
- Docker and Docker Compose

## Run Locally

### Prerequisites

- Docker
- Docker Compose
- `make`

### Setup

Copy the example env file:

```bash
cp .env.example .env
```

Set at minimum:

- `DATABASE_URL`
- `REDIS_URL`
- `AUDIT_HMAC_KEY`
- `PSEUDONYM_SECRET_KEY`
- `KEY_BACKEND`
- `LOCAL_VAULT_KEY` when using local development keys

Start the stack:

```bash
make up
```

Verify health:

```bash
curl http://localhost:8000/health
```

Useful commands:

```bash
make logs
make down
make rebuild
make test
make lint
```

## SDKs

Ironpass already includes client SDK scaffolding for:

- Python: `sdk/python`
- Node.js / TypeScript: `sdk/nodejs`

These SDKs target the explicit scan flow and help agents integrate without hand-writing HTTP requests.

## Documentation

- `Architecture.md` contains the detailed architecture and build plan
- `engine/rulesets/definitions/` contains the active YAML rulesets

## What This Project Demonstrates

- security-minded middleware for AI systems
- policy-driven handling of PII and sensitive data
- multi-layer detection design with deterministic and NER-based checks
- product thinking around compliance infrastructure for agentic systems
- cross-language integration surfaces through Python and Node SDKs

## Current Status

Ironpass has a meaningful working foundation today: the proxy layer, detection engine, ruleset loader, SDK scaffolding, Docker setup, and dashboard shell are all present in the repo.

It is still clearly an active MVP, not a finished production platform. Some architecture surfaces are broader than the code that is currently implemented, and some endpoints remain partial or TODO-driven. The repo is strongest today as a serious security infrastructure prototype for AI agents.

## License

Proprietary. All rights reserved.

