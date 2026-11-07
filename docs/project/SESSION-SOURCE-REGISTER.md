# Session and Source Register

**Last review:** 2026-10-28  
**Purpose:** Track the provenance of OpenWorld planning decisions and previous conversations without treating inaccessible links as read transcripts.

## A. External conversation URLs supplied by the project owner

The first request supplied two **unique** URLs, with the first repeated. Subsequent requests supplied two further **distinct** share URLs. Attempts to read their full transcripts via the available reader were unsuccessful. No complete transcript was independently verified.

| Source ID | Shared link | Status | Eligible for transcript-derived claims? |
|---|---|---|---|
| CHAT-SHARE-001 | https://chatgpt.com/s/t_6ae211da5b6481918229efe3a872998c | **PENDING_ACCESS** — content not retrievable | **No** |
| CHAT-SHARE-002 | https://chatgpt.com/s/t_6ae2123fe370819195aff2f1f75b60ff | **PENDING_ACCESS** — content not retrievable | **No** |
| CHAT-SHARE-003 | https://chatgpt.com/share/6ae21436-a858-83ec-b90e-c55e0f507b06 | **PENDING_ACCESS** — full transcript unreadable; owner-supplied mathematical excerpt available separately | **No** |
| CHAT-SHARE-004 | https://chatgpt.com/share/6ae214d5-8860-83ec-b076-f7834ec8a002 | **PENDING_ACCESS** — full transcript unreadable; active OpenWorld discussion visible independently | **No** |

A duplicate occurrence of CHAT-SHARE-001 is not a third source. The owner's visible selected mathematical excerpt for CHAT-SHARE-003 and the visible OpenWorld discussion relevant to CHAT-SHARE-004 are **not verified full transcript exports**. Do not infer unseen topics, participants, decisions or progress from any URL.

## B. Sources actually used in this synthesis

| Source ID | Source | Coverage and evidence strength |
|---|---|---|
| OPENWORLD-CURRENT-CONVERSATION | OpenWorld project working conversation visible in the active task | Design discussions and reported prototype results; not independent evidence |
| GITHUB-MAIN | https://github.com/CocAgent/OpenWorld | Tracked source, contracts and repository history |
| GITHUB-PR-007 | https://github.com/CocAgent/OpenWorld/pull/7 | Initial public bootstrap |
| GITHUB-PR-008 | https://github.com/CocAgent/OpenWorld/pull/8 | Proposed RFC-006 contracts |
| GITHUB-PR-009 | https://github.com/CocAgent/OpenWorld/pull/9 | HM-P1e code and authored tests |
| GITHUB-PR-010 | https://github.com/CocAgent/OpenWorld/pull/10 | W5 benchmark and authored tests |
| GITHUB-GATE-011 | https://github.com/CocAgent/OpenWorld/issues/11 | Pending independent merged-main verification |
| GITHUB-PR-014 | https://github.com/CocAgent/OpenWorld/pull/14 | RFC-007 mathematical research |
| GITHUB-W2-P0-015 | https://github.com/CocAgent/OpenWorld/issues/15 | Bounded MathKernel P0 implementation |
| GITHUB-PR-017 | https://github.com/CocAgent/OpenWorld/pull/17 | Experimental compositional fixture, merged separately from acceptance gates |

## C. Safe import procedure for an unavailable shared transcript

1. Obtain an authorized export/text of the exact conversation or a genuinely accessible shared page.
2. Verify title, authorship/source identity, date and completeness.
3. Screen private or proprietary data, credentials, tool/system content and third-party rights.
4. Extract decisions into the [Decision Ledger](DECISION-LEDGER.md) with exact source IDs.
5. Deduplicate and resolve contradictions instead of silently choosing a newer statement.
6. Preserve unverified claims and negative results with explicit limitations.
7. Submit a reviewed English PR before incorporating any additional transcript-derived claims.

**Current result:** Four distinct shared URLs are recorded as pending-access; their complete transcripts have **not** been ingested. Only actually visible excerpts, discussions, and checked repository files informed the corresponding proposals and research fixture.

## D. Owner-supplied session extracts uploaded for the 2026-10-28 literature and synthesis update

Six text attachments were actually available to read in this task. They comprise **five distinct byte sequences**; `Pasted text (3).txt` and `Pasted text (4).txt` have the same SHA-256. The files are user-supplied **conversation extracts**, not independently authenticated complete exports from the linked ChatGPT Share URLs. The unedited raw uploads are **not copied into the public repository**.

| Local attachment label | SHA-256 | Topic summarized | Source status |
|---|---|---|---|
| `Pasted text(6).txt` | `a904a4fbf9566dc59a50a323a551ed0d77df4255223561ec10b4f6e48728e42f` | Early fictional world-war concept, POSG, Lie groups, gameplay | OWNER_UPLOAD_EXCERPT |
| `Pasted text (2)(1).txt` | `1a428c5846ac0cdba85233ab61271d48f17a02e0c46e9cf27cab932147b05956` | AHappy Open World community/local-first/mod/agent vision | OWNER_UPLOAD_EXCERPT |
| `Pasted text (3).txt` | `5e71f57d8a16cc0af1797521281d1446c002d4b8b8f4e9dadabc3ab90897b5af` | Independent OpenWorld and external project references | OWNER_UPLOAD_EXCERPT |
| `Pasted text (4).txt` | `5e71f57d8a16cc0af1797521281d1446c002d4b8b8f4e9dadabc3ab90897b5af` | **Exact duplicate** of the preceding file | DEDUPLICATED |
| `Pasted text (5).txt` | `b1e3606a97e75e13f0a0ae79276fb638e0a372d85ac8a8cebec16866c5a90234` | Co-evolution, world genome, institutions, trust and quality-diversity | OWNER_UPLOAD_EXCERPT |
| `Pasted text (6).txt` | `586ba84e59b41934671c9a5a1e3e8eae755319e5e78c086fcd82932ce0cd0276` | Open Civilization Protocol, categorical foundations, Markov categories | OWNER_UPLOAD_EXCERPT |

For synthesis and status reconciliation see [SESSION-SYNTHESIS-20261028.md](SESSION-SYNTHESIS-20261028.md); for independently checked primary literature see [the research map](../research/RELATED-RESEARCH-AND-PROJECTS.md). Upload excerpts support only the content they visibly contain. Previously unviewable ChatGPT Share links above remain **PENDING_ACCESS** for their *full transcripts*. Do not infer extra decisions or test results from the URL names.
