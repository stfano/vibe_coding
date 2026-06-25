# Medical Safety Policy

Doctor Chat is clinician-support software. It must not act as an autonomous diagnostic authority or a public symptom checker.

The current retrieved path can generate source-grounded clinician-support answers from reviewed `ready` knowledge documents. All generated behavior must preserve these rules:

- Do not present generated content as a replacement for clinician judgment.
- Do not provide definitive diagnoses without sufficient source-grounded clinical context.
- Use citations for medical claims when RAG is active.
- Route emergency or red-flag scenarios to urgent escalation guidance.
- Do not invent guidelines, contraindications, sources, or medication doses.
- Do not expose hidden chain-of-thought. Expose graph path, node summaries, retrieved sources, and model metadata instead.
- Use synthetic PHI only in tests and seed data.
- Retrieved LLM answers must pass deterministic post-synthesis grounding review
  before they are returned as normal retrieved answers.

External public Q&A, including HiDoc sample data, is candidate/evaluation
content unless explicit permission and clinical approval exist. It must remain
`needs_review` until reviewed, and default retrieval must use only `ready`
documents. `disabled` documents must never be returned by retrieval.

Retrieval verification tools may show snippets and citation metadata, but they
must not synthesize medical advice. Red-flag queries are suppressed from
candidate Q&A retrieval and routed to urgent escalation behavior by the minimal
chat safety router.

The chat graph now checks generated retrieved answers after synthesis. The
review fails answers that omit known retrieved citation IDs, cite unknown source
IDs, use obvious autonomous diagnosis language, or introduce unsupported
prescription/dose language. A failed review returns a safe grounding-failure
fallback while preserving citations, retrieved source IDs, model name, prompt
version, and review metadata for operator debugging.
