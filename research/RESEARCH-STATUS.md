# Research status

The OpenWorld team previously explored compact genome/state formats, generative stochastic replay (Psi-Memory), exact-event separation, batched SQLite runtimes (HM-P1c) and online ensemble predictors (HM-P1d).

These are **historical local experiments**, not validated product performance. Their archived ZIP files are intentionally excluded from the public bootstrap while ownership, third-party licensing, secrets, reproducibility and data protection are reviewed.

## Open questions

1. Which small memory representations preserve decision quality for a specified task family?
2. Under what drift and activity patterns do adaptive predictors outperform simpler estimators?
3. Can exact evidence and cross-agent collaboration coexist with owner-controlled privacy?
4. What fraction of measured cost comes from storage overhead, inference and reconstruction?
5. How can we verify generated state without inventing historical events?

## Evidence rules

Never silently discard negative experiments. A fair comparison must disclose what information each baseline preserves and what queries it can answer. Distinguish storage under compaction from online footprint including WAL. Do not extrapolate toy benchmark numbers to active billion-agent capacity.
