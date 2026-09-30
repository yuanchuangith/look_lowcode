# Global Business Graph Contract (0.5.0)

## Runtime and compatibility

Local stdio registers **41** tools: 16 core, 5 CPM, 7 Schema, 7 source, **6 graph**. HTTP registers the same 16 core tools and no graph tools. No graph database service, browser UI or NetworkX dependency is introduced.

The service now uses BusinessGraphStore in business_graph_store.py. The old JSON module remains only as a v2 validator/legacy compatibility implementation and its regression suite; the runtime does not dual-write JSON. Old search/upsert/invalidate inputs and legacy return fields remain accepted. V3 upsert accepts canonical entities, independent facts and complete evidence support sets; unknown stable identities become pending tasks, not guessed identities.

Business keywords also resolve roots through case conclusions/keys and legacy keywords, with a 1000-case/1-second seed budget and explicit query_complete status. Common typed API route templates are accepted without allowing query-value payloads.

The authoritative input contract and example are in skills/gxp-lowcode-debug/references/business-logic-graph.md and tests/fixtures/business_graph_cases.json. New local query tools are get_business_graph, trace_business_data_flow and analyze_business_graph. Canonical IDs include scope and environment; RefId/node keys and typed data object keys, not labels or publication versions, determine identity. Explicit GUIDs are normalized, display aliases retained, and different schemas/data sources/environments never name-merge.

## Store and evidence lifecycle

business-graph.sqlite3 lives in the existing system data directory, with Python-standard-library SQLite, foreign keys, WAL and 5-second lock wait. Entities, cases/observations, facts, evidence, complete supports/dependencies, catalogs, pending tasks and audit are separate tables. Evidence bodies are stored once per observation with references from facts, not repeated inline per edge. Transactional observation replacement supersedes only that case's active support. Independent support survives case invalidation; dependency changes stale only matching support sets, and facts remain current while at least one complete support is active. Returned granularity/binding metadata comes from an active support, not a revoked latest fact description.

First initialization imports existing JSON and .legacy-v1.json under a migration lock into a temporary database, records source fingerprints, isolates per-record failures with savepoints, runs quick_check and atomically publishes. Original files are not moved, rewritten, deleted or dual-written. Stable RefId/node identities can migrate; old table/field/report labels without datasource/Schema/component identity stay review-only, while safe old cases remain searchable. Missing evidence, environment or fingerprints are not invented. Malformed raw payloads are not copied into SQLite.

The graph cache is metadata-only. Whitelist and text gates reject credentials, connection details, raw records, complete parameters and SQL/generated-source bodies. Mermaid is generated from validated structure with escaped labels. Cache/locking/corruption/provider failures do not authorize platform/database writes or JSON fallback; normal read-only diagnosis continues.

## Projections, budgets and completeness

Business projection includes confirmed dependencies and structural context. Data projection excludes contains/belongs_to and unbound calls; only verified production/read/transform/display/mapping edges participate. Reads flow data→consumer, writes producer→data. Field-level mapping requires two stable fields and a structured mapping fingerprint; action/table/report context stays dataset_level. Static paths are explicitly not runtime execution.

Weak components, BFS paths and iterative SCC/condensation use the standard library and retain actual feedback edges. Boundaries and independent entities are not bugs. Isolated directory entities are valid. Gaps distinguish missing/expired evidence, unresolved identity, legal boundaries and independent business.

Neighborhood defaults to 2 and caps at 5 hops, 200 nodes, 400 edges and 256 KiB; path depth defaults to 8 and caps at 20 with at most 5 paths. Evidence bundles are never sliced; whole additional bundles may be omitted with evidence_page_complete=false. Paths missing budgeted nodes/edges are omitted whole. Frontiers enable continuation. For response-truncated parallel edges, next_edge_cursor continues the same neighborhood; restart if graph_revision changes. Analysis checks the declared scope before claiming isolation; bounded incomplete adjacency returns status=incomplete and no real-island claims. Scope scans cap at 10000 entities/20000 active facts. Sampled membership reports size/truncation. Coverage denominator is only on-demand materialized known catalog identities and declared snapshot versions, never unknown platform completeness.

A per-user-request UUID shared by get/analyze enforces persisted budgets: at most 3 existing catalog lookups, 1 hop, 30 seconds, no recursion, no business-row queries or automatic full refresh. Provider reads only fresh existing CPM/Schema/source metadata. Unknown/stale/missing/timeout/invalid proof yields a deferred task; successful lookup reuses the same transactional merge. Exact current publication confirmation remains a normal targeted read-only diagnosis step, not a guessed catalog edge.

## Verification commands

- Run tests with PYTHONPATH=mcp;tests and canonical Windows TEMP/TMP.
- scripts/verify_mcp.py checks actual Node initialize/ping/tools-list and 41 unique tools without business calls.
- scripts/verify_business_graph_stdio.py exercises all six graph tools against a temporary cache and deliberately missing business-database configuration using sanitized A→B→C→D fixtures, scoped invalidation and v2 compatibility.
- scripts/verify_accuracy_stdio.py retains current diagnostic/HTTP-registry fixture checks (41 local/16 HTTP-registry; the latter is not remote deployment verification).
- Install through scripts/install_codex_plugin.py; verify the installed launcher, plugin list and CPM version/status. No live business fact fixture is written to the real cache, and no snapshot refresh is required.

## Global graph release verification (2026-09-30)

- Implementation is released as 0.5.0. The repository installer installed and enabled 0.5.0+codex.local-20260930-053527 in look-lowcode-local; codex plugin list confirmed the installed version and enabled state.
- All 100 related graph/catalog, compatibility, tool registration, Skill, HTTP and installer/entrypoint tests passed. The final full suite ran 297 tests: 291 passed, 3 opt-in skips and the same 3 pre-existing test_environment.py errors documented below. Environment configuration/diagnosis was not changed by this graph implementation.
- The installed Node launcher passed initialize/ping/tools-list with 41 tools. All six graph tools passed 13 actual MCP protocol calls against sanitized temporary fixtures, including A→B→C→D fusion, whole support bundles, scoped invalidation and old input compatibility. No fixture fact was written to the real cache.
- Installed-source diagnostic fixtures passed six calls each for the 41-tool local registry and 16-tool HTTP registry. The HTTP check is a stdio fixture of registration, not verification of a deployed remote HTTP server. The installed launcher also passed its metadata knowledge call without business database access.
- Actual search/get protocol calls initialized the real business-graph.sqlite3 and verified repeat initialization is idempotent. The existing v2 source has no facts; the one incomplete legacy record remains a pending review task (legacy_review_required=true), with zero promoted entities/facts/supports. Both original JSON files retained identical SHA-256 hashes. SQLite quick_check passed, foreign_key_check returned no violations, and journal_mode is WAL. No business database query, platform write or credential configuration change was requested by these cache checks.
- CPM is 0.3.1. Status reports an existing stale snapshot, TTL 1800 seconds and three recorded failures; this upgrade did not refresh it or alter credentials. Stale catalogs remain deferred rather than becoming guessed evidence.
- Skill validation and git diff --check passed. Start a new Codex thread to load the updated Skill and 41-tool MCP registration. The infrastructure is complete; coverage of unknown platform business relationships is not claimed, and archived facts still require genuine current read-only evidence.

## Post-release regression corrections (2026-09-30)

- Additional review reproduced three gaps not covered by the initial release tests: partial field/report catalog lookups replaced sibling relations, terminal paths at exactly max_depth were omitted, and exact report lookup missed components after the first 20 entries.
- Catalog observation identity now uses the requested seed, keeping table/page and individual field/report support sets independent. Repeated observations remain idempotent; a changed snapshot version still invalidates all affected old supports. Existing table/page/source case keys remain compatible. Previously superseded observations remain historical; missing relations require a fresh lookup against current catalog evidence rather than automatic reactivation.
- Upstream/downstream traversal recognizes terminal paths before applying the expansion depth limit. Paths with remaining successors still report truncation and a continuation frontier.
- Exact component selection precedes the 20-component expansion cap. Report lookups return only the unique requested component and its owner; missing or ambiguous identities remain pending. Page expansion remains capped at 20.
- Four new regression tests reproduce these failures before the fix and pass afterward; 95 graph, catalog, legacy compatibility, server and local-entrypoint tests passed. Protocol verification now also checks depth-limit terminal paths in both directions.
- The repository installer installed and enabled 0.5.0+codex.local-20260930-060833. All four new regression tests also passed against the installed Python modules; the installed Node launcher passed initialize/ping/tools-list (41 tools) and all 15 graph protocol calls. Plugin manifest validation and git diff --check passed. CPM remains 0.3.1 with the existing stale snapshot; no refresh was requested. A new Codex thread loads the corrected runtime.

## Stage-one history

The following reports concern the earlier JSON case cache only. Their 38-tool and 0.4.x results do not validate the global graph implementation.


## Verification (2026-09-29)

- 25 graph unit tests passed; registration/service and Skill contracts passed.
- Full suite: 259 tests, 253 passed, 3 opt-in live skips, 3 existing errors in test_environment.py. All three also reproduce on an isolated unmodified HEAD d7bbae5: missing DatabaseConfig.environment, missing diagnosis environment output, and the absent pre-query environment gate. No graph test failed.
- Actual Node launcher initialize/ping/tools-list returned 38 tools. Fresh MCP fixture sessions returned 38 local / 16 HTTP-registry tools and passed six calls each. The HTTP registry test uses stdio transport; it is not remote deployment verification.
- Six real graph MCP protocol calls passed with a temporary cache and deliberately missing database configuration. Skill validation and whitespace checks passed.
- This change updates repository source and plugin version 0.4.0; it does not reinstall the existing local plugin or validate live business behavior.

## Upgrade verification (2026-09-30)

- The graph suite now has 32 passing tests; graph, registration, Skill and HTTP contracts total 49 passing tests. Skill and plugin manifest validators passed.
- Full suite: 266 tests, 258 passed, 3 live skips, 3 existing test_environment.py errors, and 2 Windows short-TEMP-path comparison failures. Both path failures passed when rerun with the canonical user-local TEMP directory. Environment diagnosis/configuration is outside this graph upgrade.
- The repository installer installed and enabled 0.4.1+codex.local-20260930-015512. The installed Node launcher passed initialize/ping/tools-list with 38 tools. CPM version is 0.3.1; status reports TTL 1800s and an existing stale snapshot, which was not refreshed by this upgrade.
- A real search_business_logic_graph protocol call migrated the current machine's old script cache. Its one legacy confirmed record lacks the new evidence contract, so it was not promoted; the original file was retained byte-for-byte in business-logic-graph.legacy-v1.json, and legacy_review_required=true was returned. No business database or platform design was written.
- A new Codex thread is required to load the updated Skill and three graph tools. Real business evidence for the archived record still requires normal read-only re-verification, not invented metadata.
