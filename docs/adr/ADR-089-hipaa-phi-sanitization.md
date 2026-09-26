# ADR 089: HIPAA PHI Sanitization on Export
## Context
Downstream analytical ingestion pipelines are not HIPAA-cleared for raw Personally Identifiable Information (PII) or Protected Health Information (PHI).
## Decision
Every exported patient medical summary MUST sanitize or completely omit the `ssn` and `date_of_birth` fields from the exported payload dictionary prior to broadcast.
## Status
Accepted
