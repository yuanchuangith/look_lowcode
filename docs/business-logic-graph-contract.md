# Local business logic graph

The three graph tools are local stdio tools. The HTTP registry remains the 16 core read-only tools. Local stdio discovery is 38 tools: 16 core, 5 CPM, 7 Schema, 7 source, and 3 graph tools.

The graph is a user-local JSON cache. It stores confirmed conclusions, stable action/page/group/node anchors, published design identity, table/view/field metadata, structured nodes and edges, bounded Mermaid, and opaque evidence fingerprints. It does not store business records, credentials, connection information, complete parameters, raw SQL, source text or complete generated C#.

`search_business_logic_graph` is a lead lookup and always requires rechecking the current published copy. `upsert_business_logic_graph` accepts only `confirmed_static`, `confirmed_data`, or `runtime_verified` relations with published-design, control-flow and Schema or read-only data evidence (plus read-only/runtime evidence for stronger statuses). Repeated writes are idempotent. Changed evidence or published design supersedes the active revision. `invalidate_business_logic_graph` preserves an audit entry and marks the relation stale or invalidated.

The complete field contract, query parameters, evidence gates, size limits and supported migration wrappers are maintained in the [Skill reference](../skills/gxp-lowcode-debug/references/business-logic-graph.md), which is included in the plugin payload. Confirmation status and lifecycle are separate fields. relation_id is derived from environment/relation_key/primary RefId; evidence_fingerprint is derived from the normalized evidence chain. Caller-supplied IDs/fingerprints must match these computed values.

The store reuses the existing cross-platform file lock and atomic JSON writer. A relation is limited to 64 KiB, the file to 16 MiB, and a search response to 256 KiB. Failed atomic writes/migrations preserve the prior file. Corruption, unknown versions, lock failures and migration failures return available=false at the service boundary without constructing a database connection. Migration reports imported/skipped/rejected counts and never invents missing anchors or evidence.

The [sanitized training fixture](../tests/fixtures/business_logic_graph_training.json) covers cancellation/closure → task status → close_date → statistics view → report display. It contains no real records or connection information and does not establish real business behavior.

## Verification (2026-09-29)

- 25 graph unit tests passed; registration/service and Skill contracts passed.
- Full suite: 259 tests, 253 passed, 3 opt-in live skips, 3 existing errors in test_environment.py. All three also reproduce on an isolated unmodified HEAD d7bbae5: missing DatabaseConfig.environment, missing diagnosis environment output, and the absent pre-query environment gate. No graph test failed.
- Actual Node launcher initialize/ping/tools-list returned 38 tools. Fresh MCP fixture sessions returned 38 local / 16 HTTP-registry tools and passed six calls each. The HTTP registry test uses stdio transport; it is not remote deployment verification.
- Six real graph MCP protocol calls passed with a temporary cache and deliberately missing database configuration. Skill validation and whitespace checks passed.
- This change updates repository source and plugin version 0.4.0; it does not reinstall the existing local plugin or validate live business behavior.
