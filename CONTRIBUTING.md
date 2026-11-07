# Contributing to OpenWorld

We welcome code, proofs, reproducible benchmarks, documentation and constructive reviews.

English is the canonical engineering language. Selected **explanatory** Vietnamese onboarding pages are permitted only in [docs/vi](docs/vi/README.md) under ADR-006; normative RFCs, schemas, code, issues and PRs remain English. Review criticism via [the evidence-based dispositions](docs/GOVERNANCE-REVIEW-POLICY.md). Discuss significant architectural changes in an issue first. Use a topic branch and a small PR; changes to shared interfaces need an Architecture Decision Record.

Run locally:

```bash
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

For algorithms, report assumptions, comparison baselines, negative findings, seeds and limitations. For performance, include hardware, environment, actual disk use (including SQLite WAL), peak RAM and latency distributions where appropriate. No paid CI, model API or cloud service is required for a valid contribution.

Do not publish keys, private logs, personal information, or unreviewed third-party research archives. For vulnerabilities, follow [SECURITY.md](SECURITY.md). See [workstreams](docs/WORKSTREAMS.md).
