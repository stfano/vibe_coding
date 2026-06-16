# Local Development

## Prerequisites

- Docker Desktop with Docker Compose
- Node.js 20+ if running the frontend outside Docker
- Python 3.12+ if running the backend outside Docker

## Environment

Create a local environment file:

```bash
cp .env.example .env
```

Update the placeholder passwords and `DJANGO_SECRET_KEY` for your machine. Do not commit `.env`.

For Supabase-backed development or deployment, set either `DATABASE_URL` or `SUPABASE_DATABASE_URL` to your Supabase Postgres connection string. Include `sslmode=require` unless your Supabase connection string already includes it. If both database URL variables are empty, the backend falls back to local SQLite.

Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` when frontend or backend features need Supabase project metadata. The publishable key is safe for client-side use, but service-role keys and database passwords must remain only in untracked local environment files.

MVP vector retrieval uses Supabase/Postgres `pgvector`. The SQLite fallback is
fine for non-RAG backend work and unit tests, but document embedding search
requires `DATABASE_URL` or `SUPABASE_DATABASE_URL` to point at a Postgres
database with the `vector` extension enabled.

## Start The Stack

```bash
docker compose up --build
```

Main URLs:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health/
- Backend chat: http://localhost:8000/api/chat/messages/
- Django admin: http://localhost:8000/admin/
- MinIO console: http://localhost:9001
- Embedding service health: http://localhost:8080/health

Optional Ollama service:

```bash
docker compose --profile llm up ollama
```

## Backend Commands

Run migrations:

```bash
docker compose exec backend python manage.py migrate
```

Create a local admin user:

```bash
docker compose exec backend python manage.py createsuperuser
```

Run tests:

```bash
docker compose exec backend pytest
```

Run the HiDoc pediatric sample ingestion against the configured database:

```bash
docker compose exec backend python manage.py ingest_hidoc_qna --department 소아과 --limit 100 --workers 5 --mode sample
```

Run full HiDoc department ingestion:

```bash
docker compose exec backend python manage.py ingest_hidoc_qna --all --workers 10 --mode full
```

Monitor ingestion progress in real time:

```bash
tail -f ingestion.log
```

For parser/network verification without database writes:

```bash
docker compose exec backend python manage.py ingest_hidoc_qna --department 소아과 --limit 5 --workers 2 --mode sample --dry-run --max-pages 1 --skip-total-discovery
```

Run backend tests outside Docker:

```bash
cd backend
python -m pip install -r requirements.txt
pytest
```

## Frontend Commands

Run the frontend build outside Docker:

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

## Troubleshooting

If Compose cannot find environment variables, confirm `.env` exists at the repository root.

If you switch from SQLite to Supabase, run migrations after setting `DATABASE_URL` or `SUPABASE_DATABASE_URL`:

```bash
docker compose exec backend python manage.py migrate
```

If the frontend shows `Backend unavailable`, confirm the backend is running and `VITE_API_BASE_URL` points to the backend origin.
