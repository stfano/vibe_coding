import { useEffect, useState } from "react";

import {
  fetchEnvelope,
  type EvaluationRunDetailData,
  type EvaluationRunListData,
  type EvaluationRunSummary,
} from "./api";

export function EvaluationPanel() {
  const [runs, setRuns] = useState<EvaluationRunSummary[]>([]);
  const [selected, setSelected] = useState<EvaluationRunDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadRuns() {
    setLoading(true);
    setError(null);
    try {
      const body = await fetchEnvelope<EvaluationRunListData>("/api/evaluation/runs/");
      setRuns(body.data?.results ?? []);
      if (body.data?.results.length) {
        await loadRunDetail(body.data.results[0].id);
      } else {
        setSelected(null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load evaluation runs");
    } finally {
      setLoading(false);
    }
  }

  async function loadRunDetail(runId: number) {
    setDetailLoading(true);
    setError(null);
    try {
      const body = await fetchEnvelope<EvaluationRunDetailData>(`/api/evaluation/runs/${runId}/`);
      setSelected(body.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load evaluation run detail");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, []);

  const failedResults = selected?.results.filter((result) => result.status === "failed") ?? [];

  return (
    <section className="panel ops-panel">
      <div className="panel-title-row">
        <div>
          <h2>Evaluation Runs</h2>
          <p className="muted">Golden-set chat/RAG smoke tests. Full crawling is not triggered.</p>
        </div>
        <button disabled={loading} onClick={() => void loadRuns()} type="button">
          {loading ? "Loading" : "Refresh"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {!loading && runs.length === 0 && <div className="empty-state">No evaluation runs yet.</div>}

      <div className="ops-list">
        {runs.map((run) => (
          <button
            className={`document-row ${selected?.run.id === run.id ? "document-row-active" : ""}`}
            key={run.id}
            onClick={() => void loadRunDetail(run.id)}
            type="button"
          >
            <span>
              <strong>
                {run.dataset} / {run.status}
              </strong>
              <small>
                pass {run.passed_cases} / fail {run.failed_cases} / skip {run.skipped_cases}
              </small>
            </span>
            <em>{new Date(run.created_at).toLocaleString()}</em>
          </button>
        ))}
      </div>

      {selected && (
        <article className="detail-block">
          <div className="message-meta">
            <span>{selected.run.llm_provider}</span>
            <span>{selected.run.model_name || "model unknown"}</span>
            <span>{selected.run.prompt_version || "prompt none"}</span>
            {detailLoading && <span>loading detail</span>}
          </div>
          <h3>
            {selected.run.dataset} {selected.run.dataset_version}
          </h3>
          <dl className="health-list eval-summary">
            <div>
              <dt>Total</dt>
              <dd>{selected.run.total_cases}</dd>
            </div>
            <div>
              <dt>Passed</dt>
              <dd>{selected.run.passed_cases}</dd>
            </div>
            <div>
              <dt>Failed</dt>
              <dd>{selected.run.failed_cases}</dd>
            </div>
            <div>
              <dt>Skipped</dt>
              <dd>{selected.run.skipped_cases}</dd>
            </div>
          </dl>

          {failedResults.length > 0 ? (
            <div className="search-results">
              {failedResults.map((result) => (
                <article className="search-result-row" key={result.id}>
                  <div className="message-meta">
                    <span>{result.case_key}</span>
                    <span>{result.source_status.replace("_", " ")}</span>
                    <span>llm: {result.llm_executed ? "executed" : "not executed"}</span>
                  </div>
                  <p>{result.error_summary || failedCheckSummary(result.checks)}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="safety">No failed cases in this run.</p>
          )}
        </article>
      )}
    </section>
  );
}

function failedCheckSummary(checks: Record<string, boolean>) {
  const failed = Object.entries(checks)
    .filter(([, passed]) => !passed)
    .map(([name]) => name.replace(/_/g, " "));
  return failed.length ? `Failed checks: ${failed.join(", ")}` : "No failed check details.";
}
