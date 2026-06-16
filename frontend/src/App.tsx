import { type FormEvent, useEffect, useState } from "react";

import { apiBaseUrl, type ChatData, type Envelope, type HealthData } from "./api";
import { ReviewQueuePanel } from "./ReviewQueuePanel";
import { SearchVerificationPanel } from "./SearchVerificationPanel";

type HealthResponse = Envelope<HealthData>;
type ChatResponse = Envelope<ChatData>;

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState("Can you answer from approved local documents?");
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadHealth() {
      try {
        setLoading(true);
        setHealthError(null);
        const response = await fetch(`${apiBaseUrl}/api/health/`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Health request failed with ${response.status}`);
        }

        setHealth((await response.json()) as HealthResponse);
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        setHealthError(caught instanceof Error ? caught.message : "Unknown health check error");
      } finally {
        setLoading(false);
      }
    }

    void loadHealth();

    return () => controller.abort();
  }, []);

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message) {
      return;
    }

    try {
      setChatLoading(true);
      setChatError(null);
      const response = await fetch(`${apiBaseUrl}/api/chat/messages/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
      });

      const body = (await response.json()) as ChatResponse;
      if (!response.ok || !body.ok) {
        throw new Error(body.error?.message ?? `Chat request failed with ${response.status}`);
      }

      setChatResponse(body);
    } catch (caught) {
      setChatError(caught instanceof Error ? caught.message : "Unknown chat request error");
    } finally {
      setChatLoading(false);
    }
  }

  const dependencies = health?.data?.dependencies ?? {};

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="workspace-header">
          <div>
            <h1>Doctor Chat</h1>
            <p>Clinician support platform scaffold</p>
          </div>
          <span className={health?.ok ? "status status-ok" : "status"}>
            {loading ? "Checking" : health?.ok ? "Backend online" : "Backend unavailable"}
          </span>
        </header>

        <div className="grid">
          <section className="panel">
            <h2>Backend Health</h2>
            {loading && <p className="muted">Calling {apiBaseUrl}/api/health/</p>}
            {healthError && <p className="error">{healthError}</p>}
            {health?.data && (
              <dl className="health-list">
                <div>
                  <dt>Service</dt>
                  <dd>{health.data.service}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{health.data.status}</dd>
                </div>
                <div>
                  <dt>Version</dt>
                  <dd>{health.meta.version ?? "unknown"}</dd>
                </div>
              </dl>
            )}
          </section>

          <section className="panel">
            <h2>Local Services</h2>
            <ul className="service-list">
              {Object.entries(dependencies).map(([name, status]) => (
                <li key={name}>
                  <span>{name.replace("_", " ")}</span>
                  <strong>{status}</strong>
                </li>
              ))}
              {!loading && Object.keys(dependencies).length === 0 && (
                <li>
                  <span>No dependency metadata returned</span>
                  <strong>check backend</strong>
                </li>
              )}
            </ul>
          </section>

          <ReviewQueuePanel />

          <SearchVerificationPanel />

          <section className="panel chat-panel">
            <h2>Chat Workspace</h2>
            <div className="chat-transcript">
              {chatResponse?.data ? (
                <article className="assistant-message">
                  <div className="message-meta">
                    <span>{chatResponse.data.source_status.replace(/_/g, " ")}</span>
                    <span>graph: {chatResponse.data.graph.executed ? "executed" : "not executed"}</span>
                  </div>
                  <p>{chatResponse.data.answer}</p>
                  <p className="safety">{chatResponse.data.safety_notice}</p>
                </article>
              ) : (
                <div className="empty-state">No chat response yet.</div>
              )}
            </div>
            {chatError && <p className="error">{chatError}</p>}
            <form className="input-row" onSubmit={submitChat}>
              <textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                rows={3}
              />
              <button disabled={chatLoading || !chatInput.trim()} type="submit">
                {chatLoading ? "Sending" : "Send"}
              </button>
            </form>
          </section>
        </div>
      </section>
    </main>
  );
}
