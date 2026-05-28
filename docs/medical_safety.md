# Medical Safety Policy

Doctor Chat is clinician-support software. It must not act as an autonomous diagnostic authority or a public symptom checker.

Milestone 1 does not generate medical answers. Later milestones must preserve these rules:

- Do not present generated content as a replacement for clinician judgment.
- Do not provide definitive diagnoses without sufficient source-grounded clinical context.
- Use citations for medical claims when RAG is active.
- Route emergency or red-flag scenarios to urgent escalation guidance.
- Do not invent guidelines, contraindications, sources, or medication doses.
- Do not expose hidden chain-of-thought. Expose graph path, node summaries, retrieved sources, and model metadata instead.
- Use synthetic PHI only in tests and seed data.
