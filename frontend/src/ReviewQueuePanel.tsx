import { useEffect, useState } from "react";

import {
  fetchEnvelope,
  type KnowledgeDocumentDetailData,
  type KnowledgeDocumentListData,
  type KnowledgeDocumentSummary,
} from "./api";

const statuses: KnowledgeDocumentSummary["status"][] = ["needs_review", "ready", "disabled"];

export function ReviewQueuePanel() {
  const [status, setStatus] = useState<KnowledgeDocumentSummary["status"]>("needs_review");
  const [documents, setDocuments] = useState<KnowledgeDocumentSummary[]>([]);
  const [selected, setSelected] = useState<KnowledgeDocumentDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionPendingId, setActionPendingId] = useState<number | null>(null);

  async function loadDocuments(nextStatus = status) {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        source: "hidoc",
        department_code: "PD000",
        status: nextStatus,
        page_size: "10",
      });
      const body = await fetchEnvelope<KnowledgeDocumentListData>(`/api/knowledge/documents/?${query}`);
      setDocuments(body.data?.results ?? []);
      if (body.data?.results.length) {
        await loadDetail(body.data.results[0].id);
      } else {
        setSelected(null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load review queue");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(documentId: number) {
    setDetailLoading(true);
    setError(null);
    try {
      const body = await fetchEnvelope<KnowledgeDocumentDetailData>(
        `/api/knowledge/documents/${documentId}/`,
      );
      setSelected(body.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load document detail");
    } finally {
      setDetailLoading(false);
    }
  }

  async function updateStatus(documentId: number, nextStatus: KnowledgeDocumentSummary["status"]) {
    setActionPendingId(documentId);
    setError(null);
    try {
      await fetchEnvelope<KnowledgeDocumentSummary>(`/api/knowledge/documents/${documentId}/status/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      await loadDocuments(status);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update document status");
    } finally {
      setActionPendingId(null);
    }
  }

  useEffect(() => {
    void loadDocuments(status);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="panel ops-panel">
      <div className="panel-title-row">
        <div>
          <h2>Review Queue</h2>
          <p className="muted">HiDoc PD000 sample only. Full crawl controls are not exposed.</p>
        </div>
        <select
          aria-label="Document status"
          value={status}
          onChange={(event) => {
            const nextStatus = event.target.value as KnowledgeDocumentSummary["status"];
            setStatus(nextStatus);
            void loadDocuments(nextStatus);
          }}
        >
          {statuses.map((option) => (
            <option key={option} value={option}>
              {option.replace("_", " ")}
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="muted">Loading review queue...</p>}
      {error && <p className="error">{error}</p>}
      {!loading && documents.length === 0 && <div className="empty-state">No documents in this queue.</div>}

      <div className="ops-list">
        {documents.map((document) => (
          <button
            className={`document-row ${selected?.document.id === document.id ? "document-row-active" : ""}`}
            key={document.id}
            onClick={() => void loadDetail(document.id)}
            type="button"
          >
            <span>
              <strong>{document.title}</strong>
              <small>
                {document.source} / {document.department_code} / chunks {document.chunk_count}
              </small>
            </span>
            <em>{document.status.replace("_", " ")}</em>
          </button>
        ))}
      </div>

      {selected && (
        <article className="detail-block">
          <div className="message-meta">
            <span>{selected.document.source_license_status.replace("_", " ")}</span>
            <span>{selected.document.source_external_id}</span>
            {detailLoading && <span>loading detail</span>}
          </div>
          <h3>{selected.document.title}</h3>
          <a href={selected.document.source_url} rel="noreferrer" target="_blank">
            {selected.document.source_url}
          </a>
          {selected.external_qna_record && (
            <div className="qa-preview">
              <p>
                <strong>Question</strong> {selected.external_qna_record.question_body}
              </p>
              <p>
                <strong>Answer</strong> {selected.external_qna_record.answer_body}
              </p>
            </div>
          )}
          <div className="action-row">
            {statuses.map((option) => (
              <button
                disabled={actionPendingId === selected.document.id || selected.document.status === option}
                key={option}
                onClick={() => void updateStatus(selected.document.id, option)}
                type="button"
              >
                {option.replace("_", " ")}
              </button>
            ))}
          </div>
          <div className="chunk-preview">
            {selected.chunks.map((chunk) => (
              <div key={chunk.id}>
                <strong>Chunk {chunk.chunk_index}</strong>
                <p>{chunk.text_preview}</p>
              </div>
            ))}
          </div>
        </article>
      )}
    </section>
  );
}
