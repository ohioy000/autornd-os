# Changelog

All notable changes to AutoRnD will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-09-12

### Added

- Multi-model agentic workflow engine with 5-phase sequencer (triage, plan, implement, validate, review)
- 7 engineering specialists with profile-driven system prompts
- K3 escalation autopsy pattern — reasoning model recovery when implement/validate loop exhausts
- Risk-based review team composition (critical → all specialists, low → single specialist)
- Plan feasibility gating — specialists review the plan before implementation tokens are spent
- Project profile system — YAML-based domain grounding with per-specialist context overrides
- Profile-aware knowledge store with ChromaDB semantic retrieval
- Episodic memory — workflow outcomes stored for future context
- REST API with sync and async workflow submission
- Dashboard with chat interface, workflow table, and profile selector
- API key authentication middleware (optional, bearer token)
- OpenRouter multi-model routing client with cost tracking and retry logic
- CLI for doc ingestion (`init-knowledge`)
- Docker support with volume mounts for profiles and docs
- Example profile (SmartFactory) with sample docs
- Full test suite (85 tests)
