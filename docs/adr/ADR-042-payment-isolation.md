# ADR 042: Multi-Tenant Payment Isolation
## Context
Our platform processes payments across isolated enterprise tenants.
## Decision
Every payment authorization event MUST include the originating tenant_id in its root payload for multi-tenant billing isolation and regulatory compliance.
## Status
Accepted
