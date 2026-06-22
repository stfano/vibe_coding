import { type FormEvent, useState } from "react";

import { fetchEnvelope, type SearchVerificationData } from "./api";

export function SearchVerificationPanel() {
  const [query, setQuery] = useState("아기 고환 물집 아기띠");
  const [topK, setTopK] = useState(5);
  const [includeNeedsReview, setIncludeNeedsReview] = useState(false);
  const [result, setResult] = useState<SearchVerificationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        query: trimmed,
        top_k: String(topK),
        source: "hidoc",
        department_code: "PD000",
        include_needs_review: String(includeNeedsReview),
      });
      const body = await fetchEnvelope<SearchVerificationData>(`/api/knowledge/search/verify/?${params}`);
      setResult(body.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to verify search");
    } finally {
      setLoading(false);
    }
  }

  const retrieval = result?.retrieval ?? result?.retrieval_metadata;

  return (
    <section className="panel ops-panel">
      <h2>Search Verification</h2>
      <p className="muted">Returns retrieval previews and citations only. No LLM answer is generated.</p>
      <form className="search-form" onSubmit={submitSearch}>
        <textarea
          aria-label="Search query"
          onChange={(event) => setQuery(event.target.value)}
          rows={3}
          value={query}
        />
        <div className="form-controls">
          <label>
            Top K
            <input
              max={20}
              min={1}
              onChange={(event) => setTopK(Number(event.target.value))}
              type="number"
              value={topK}
            />
          </label>
          <label className="checkbox-label">
            <input
              checked={includeNeedsReview}
              onChange={(event) => setIncludeNeedsReview(event.target.checked)}
              type="checkbox"
            />
            Include needs review
          </label>
          <button disabled={loading || !query.trim()} type="submit">
            {loading ? "Searching" : "Search"}
          </button>
        </div>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="verification-result">
          <div className="message-meta">
            <span>{result.source_status.replace("_", " ")}</span>
            <span>llm: {result.llm_executed ? "executed" : "not executed"}</span>
            <span>graph: {result.graph_executed ? "executed" : "not executed"}</span>
            {retrieval && (
              <>
                <span>
                  embed: {retrieval.embedding_provider ?? "unknown"} /{" "}
                  {retrieval.embedding_model || "unknown"} /{" "}
                  {retrieval.embedding_dimensions ?? "?"}d
                </span>
                <span>metric: {retrieval.vector_metric ?? "unknown"}</span>
                <span>
                  rerank:{" "}
                  {retrieval.rerank_enabled ? retrieval.rerank_model ?? "enabled" : "off"}
                </span>
                {retrieval.embedding_fallback_used && <span>embedding fallback</span>}
              </>
            )}
            {result.safety_flags.map((flag) => (
              <span key={flag}>{flag.replace("_", " ")}</span>
            ))}
          </div>
          {result.red_flag_terms?.length ? (
            <p className="safety">
              Red-flag query suppressed retrieval: {result.red_flag_terms.join(", ")}
            </p>
          ) : null}
          {result.results.length === 0 && <div className="empty-state">No matching ready chunks.</div>}
          <div className="search-results">
            {result.results.map((item) => (
              <article className="search-result-row" key={`${item.chunk_id}-${item.rank}`}>
                <div className="message-meta">
                  <span>rank {item.rank}</span>
                  <span>score {item.score.toFixed(3)}</span>
                  {item.raw_score != null && <span>raw {item.raw_score.toFixed(3)}</span>}
                  {item.rerank_score != null && <span>rerank {item.rerank_score.toFixed(3)}</span>}
                  <span>{item.document_status.replace("_", " ")}</span>
                </div>
                <p>{item.preview}</p>
                <dl className="citation-list">
                  <div>
                    <dt>Title</dt>
                    <dd>{item.citation.title ?? "unknown"}</dd>
                  </div>
                  <div>
                    <dt>Source URL</dt>
                    <dd>
                      {item.citation.source_url ? (
                        <a href={item.citation.source_url} rel="noreferrer" target="_blank">
                          {item.citation.source_url}
                        </a>
                      ) : (
                        "missing"
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>External IDs</dt>
                    <dd>
                      {item.citation.external_question_id ?? "unknown"} /{" "}
                      {item.citation.external_answer_id ?? "unknown"}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
