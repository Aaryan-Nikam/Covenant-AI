# Enrichall

Standalone recruiter email enrichment micro-tool.

Recruiters bring their own provider API keys, set priority order, and enrich candidates through single lookup or CSV batch upload.

## Quick Start

```bash
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:3001`.

## Required Setup

Create a new Supabase project and run:

```sql
-- enrichall/supabase/migrations/001_create_tables.sql
```

Then fill:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`

## API

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/providers`
- `POST /api/providers`
- `POST /api/providers/test`
- `DELETE /api/providers/:provider`
- `POST /api/enrich`
- `POST /api/enrich/batch`
- `GET /api/jobs`
- `GET /api/jobs/:id`
- `GET /api/jobs/:id/download`
- `GET /api/stats`

