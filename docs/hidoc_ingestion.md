# HiDoc Q&A Ingestion

HiDoc Q&A ingestion is implemented as a backend Django management command:

```bash
cd backend
python manage.py ingest_hidoc_qna --department 소아과 --limit 100 --workers 5 --mode sample
```

Full collection discovers department codes from the HiDoc department selector:

```bash
cd backend
python manage.py ingest_hidoc_qna --all --workers 10 --mode full
```

The command writes append-only progress logs to `ingestion.log`. Each page
entry includes mode, department, page progress, record progress, insert/update
counts, failures, and worker ID where applicable.

```bash
tail -f ingestion.log
```

Data is stored in `knowledge_externalqnarecord`, one row per answer-level Q&A
record. Repeated runs are idempotent because upsert uses the stable external ID
`hidoc:<question_id>:<answer_id>`. The separate `content_hash` changes when the
question or answer text changes.

Operational safety:

- request delay defaults to `HIDOC_REQUEST_DELAY=0.5`
- page workers default to `INGESTION_WORKERS=5`
- robots.txt is checked by default
- logs do not include raw question or answer body text
- use `--dry-run` for parser/network checks without database writes

Third-party content limitation: HiDoc Q&A content should be treated as a
candidate or evaluation corpus unless explicit permission covers ingestion,
storage, embeddings, RAG use, citations, and deployment.

## Index Sampled Q&A Into Knowledge Chunks

After the pediatric 100-record sample is ingested, convert those
`ExternalQnaRecord` rows into inspectable knowledge documents and embedded
chunks:

```bash
cd backend
python manage.py migrate
python manage.py index_external_qna --source hidoc --department-code PD000 --limit 100
```

The command creates or updates:

- `KnowledgeSource`
- `KnowledgeDocument`
- `KnowledgeChunk`
- `IndexJob`

The indexer is idempotent. Re-running the same command updates the same
document rows, replaces that document's chunks, and avoids duplicate chunks.
Each chunk stores citation metadata including source, source URL, external
question ID, external answer ID, title, department, chunk index, and source
record ID.

Indexing progress is also appended to `ingestion.log` by default, without raw
question or answer bodies:

```bash
tail -f ingestion.log
```

The default embedding provider is deterministic token hashing for local and
test runs. Configure HTTP embeddings through environment variables when the
embedding service is available:

```bash
EMBEDDING_PROVIDER=http
EMBEDDING_SERVICE_URL=http://embedding-service:8080
EMBEDDING_MODEL=mykor/KURE-v1
VECTOR_DIMENSIONS=1024
INDEXING_CHUNK_CHARS=1200
```

Search indexed chunks without synthesizing a medical answer:

```bash
cd backend
python manage.py search_knowledge --query "아기 고환 물집 아기띠" --top-k 5 --source hidoc --department-code PD000
```

The search command returns chunk previews plus citation metadata only. It does
not call an LLM and does not turn HiDoc Q&A into authoritative medical
guidance.
