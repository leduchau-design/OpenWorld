# OpenWorld roadmap

## R0 — Public foundation
- Establish a clean English monorepo and local tests.
- Define interfaces, security boundaries, a workstream map and experimental reproducibility requirements.
- Maintain historical research artifacts outside the public repository until explicitly reviewed.

## R1 — HM-P1e: adaptive memory optimization
- Select predictive adaptation only when validated benefit exceeds added cost.
- Benchmark full-history, static, discounted, ensemble and sparse modes fairly.
- Measure runtime WAL, fsync, disk, CPU, memory, latency and quality under regime shift.

## R2 — Trustworthy personal agent
- Persistent identity, consented memory, provenance-aware recall and revocable capabilities.
- Test realistic long-horizon tasks and cross-user isolation.

## R3 — Social agents and interoperability
- Sparse event graph, order guarantees, bounded agent communication and shared knowledge with explicit grants.
- Integrate MCP/A2A only after threat modeling and compatibility testing.

## R4 — Distributed evaluation
- Sharding, backups, bounded scheduling, resource budgets and total cost measurement.
- Do not extrapolate active-agent capacity from record counts alone.

## R5 — Research-aligned optional world and game tracks (proposed, not accepted release scope)

These proposals are drawn from the [session synthesis](project/SESSION-SYNTHESIS-20261028.md) and the [research map](research/RELATED-RESEARCH-AND-PROJECTS.md). They do not override R0–R4 or the independent W0/W1/W5 gate in [Issue #11](https://github.com/CocAgent/OpenWorld/issues/11).

1. **W3 offline world:** one authoritative simulation with typed observation/action, conflict resolution, resource conservation, complete replay inputs and explicitly `SIMULATED` evidence. Gate: unauthorized or conflicting commands never corrupt state.
2. **Open agent and content contracts:** validate externally authored agents/world packs in a restricted, bounded execution environment. Gate: invalid and unavailable capabilities fail closed; licenses and hashes are declared. W0 reviews before freezing any OCP/OWP syntax.
3. **Living-world research pilot (optional):** a single toy world, 3 regions, around 30 agent blueprints and 5 roles (proposal, not benchmark). Gate: ablations and holdout seeds show whether memory/institutions improve diverse behavior and user interest relative to rules-only baselines.
4. **Tactical game pilot (separate optional product hypothesis):** 2 factions, 8 commander agents, 40 fictional units and 3 terrains (proposal only). Gate: an enjoyable complete match, reproducible replay and measured cost; do not conflate with the social pilot.
5. **Evolution lab:** generate candidate policy/world-genome variants offline, compare quality-diversity and solvability before admission; never let agents deploy code or mutate the trusted core.
6. **Federation (later):** start with discovering worlds and transferring compatible blueprints/content, not external world currency, authority, inventory or historical truth.

**Resource decision:** local CPU and existing hardware first, no new paid GPU/server commitment. Research references are not implementation evidence or product promises.

## R6 — Stratified populations and genome experiments (PROPOSED, not a product milestone)

Investigate [the W2/W3 population representation proposal](research/POPULATION-REPRESENTATION-AND-AGENT-DNA.md) as an opt-in offline branch. Compare aggregate mean, histogram, finite empirical characteristic sketch and learned embeddings on common seeds, matching inference budgets, held-out partner policies and adversarially heterogeneous populations. Typed agent-genome variation requires versioned lineage, bounded traits, admission/consent and clear separation from policy weights, identity, capabilities, immutable kernel rules and exact evidence.

Gate: demonstrable task-relative benefit over simpler baselines, reproducible state transitions and no unauthorized sharing of per-agent memory. No claims of scalable learning arise from the standalone sketch implementation or counting agent blueprints.
