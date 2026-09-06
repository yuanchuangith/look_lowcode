# Progress

## Accuracy implementation 2026-09-06
- Completed repository-installer-only update to 0.3.1+codex.local-20260906-021126, enabled. All60 installed core/Skill/script source hashes match. cpm0.3.1/status pass; existing snapshot stale/TTL1800/one historical failure remains without refresh. Fresh installed35/16 fixture sessions and actual Node launcher discovery/catalog pass. Durable baseline and all three replay evidence rounds hash-verified under F:/Desktop/git/look_lowcode-backups. Final implementation results include limitations and installer-only rollback steps; no remote service or business data changed.
- Both stage gates passed against final source: 195 tests (192 passed/3 live skips),22 new-focused tests; final frozen-Skill replay candidate12/12, baseline seven heading failures. Final actual UTF-8 synthetic benchmarks and fresh MCP fixtures passed. Results and limitations recorded in docs/accuracy-implementation-results-2026-09-06.md. Durable 373-file baseline hash-verified at F:/Desktop/git/look_lowcode-backups/accuracy-20260906. Proceeding to repository-installer-only local update.
- Confirmed the installed local knowledge snapshot exposes languages and both actual DataProcessing variable elements without refresh. An inline PowerShell probe initially lost Chinese characters through its pipe; explicit UTF-8 output fixed the probe and two newly added synthetic literals. Existing multibyte paging tests already used intact Chinese strings. Final benchmarks are rerun with the corrected fixture; added explicit execution/input-type examples to the on-demand conversation reference and will rerun paired acceptance against this final contract.
- Full final suite: 195 tests, 192 passed and three opt-in live skips (12.386s). A redirected log initially used C: instead of the actual F: artifact directory, so that command did not run tests; rerun succeeded at the explicit artifact path. Skill validation passed with system Python after the plugin runtime lacked optional PyYAML. Fresh MCP fixture outputs passed; PowerShell labeled normal server stderr as NativeCommandError, so subsequent captures use subprocess return codes.
- Final paired frozen-Skill replay passed all 12 candidate cases; baseline had seven reporting-heading failures, with all decision IDs correct in both versions. Same configured model gpt-6-astra; 53.299s baseline / 48.682s candidate; zero tool calls. Fresh fixture-backed MCP sessions passed four calls each with 35 local / 16 HTTP-registry tools. This is fixed-evidence testing, not live runtime verification or a population accuracy claim.
- Final review adds Python 3.10 replay configuration fallback and budgets for ambiguous identities/value pages. A search referenced a nonexistent installer-test filename; reran searches against actual test paths, with no file changes from that error.
- Baseline saved to F:/Users/25249/AppData/Local/Temp/look-accuracy-baseline-hdpn1l_t with 373 tracked/untracked source files and hashes.
- Stage 1 passed 51 focused tests. Stage 2 first full run: 200 tests, 197 passed and 3 live integration skips. All network-looking full-suite logs were test fixtures; live checks stayed disabled.
- Early patches needed corrected hunk context/order; changes were retained and subsequent tests passed. Byte clipping initially omitted an explicitly requested C# region; restored it as priority evidence. Compact reads now summarize reference counts unless focus_fields is requested.
- First paired same-model replay: all 12 decision identifiers correct for both builds. Strict classification rubric also penalized valid clarification/pending-review responses. Raw first-round outputs are retained at F:/Users/25249/AppData/Local/Temp/look-accuracy-replay-20260906. Added documented equivalent classifications applied identically to both versions; rerun final frozen Skill before installation. No result is described as live platform validation.

## Conversation accuracy assessment 2026-09-06
- Completed seven offline probe observations and 39 existing focused tests; no business database access.
- Added the reproducible probe script and prioritized Chinese assessment. No implementation/deployment was performed; user-owned pre-existing changes remain intact.
- Inspected instructions, prior plans, dirty files, routing, canvas lookup and report contracts. Assessment only; no deployment or runtime changes.
- PowerShell patch arguments lost a final newline; switched to direct apply_patch engine invocation. A subsequent non-raw Python string expanded a newline inside a patch; retry uses a raw patch string.
- Next: isolated synthetic probes, focused regressions and a prioritized review report.

## Follow-up implementation progress 2026-09-05
- Preserved implementation baseline at F:/Users/25249/AppData/Local/Temp/look-followup-baseline-yoO80C. Added initially failing regressions for four reviewed issues; first run: 20 tests with 38 failing subcases and one error.
- P1 fixes now track compound/prefix/destructuring writes, lexical shadowing and stable query-prefix appends; response budgeting is recursive, non-mutating, UTF-8 serialized and also covers failed source-layer exits.
- Full namespace/signature queries now select constrained starts; ambiguous short names stay candidates without recursive expansion. Layer-specific content fingerprints skip unrelated artifacts but retain source/config content hashes and rename original paths. Index version upgraded to 3.
- First real benchmark exceeded +20%; profiling identified token matching and costly Path traversal. Prioritized punctuation tokens and os.walk filter evidence reduced the next build median to 3.371s (baseline 3.326s), query median to 0.866s (baseline 0.967s). Final regression and dirty-matrix checks follow before local installation.
- Tool notes: PowerShell does not expand rg path globs; switched to rg -g filters. Additional prefix-transform/rest-parameter probes failed first and were fixed without weakening candidate output.

## Follow-up release completion 2026-09-05
- Final full suite: 173 tests, 170 passed, 3 opt-in live skipped; compileall, Skill validation, plugin validation, diff check and installed source hashes pass.
- Final installed version: 0.3.1+codex.local-20260905-025922. Fresh stdio/HTTP sessions verify 35/16 tools; installed source status migrates to index v3 and golden calls remain within the 64 KiB structured payload budget.
- Follow-up fixes are local-only and did not redeploy relation policy. Business repositories remain clean; CPM snapshot remains stale with three pre-existing failures.
- Controlled paired runs were noisy on the host: the final implementation run was 6.320s build / 1.075s query median versus 5.912s / 1.353s baseline; an earlier optimized run was 3.371s / 0.866s. All build samples remain below 60s, and the 20% gate is evaluated against the stable original benchmark separately.

## Follow-up audit completion 2026-09-05
- Reproduced two priority correctness/output gaps (compound/prefix URL writes and non-hard 64 KiB output budget), plus fully-qualified entry ambiguity and irrelevant-dirty-file rebuilding. Implementation and deployment unchanged.
- Temporary metadata benchmark: unrelated 64 MiB artifact raised five-run median from 0.07135s to 0.12147s. Documentation-only change triggered one full frontend scan.
- Explained real backend route delta: one commented pseudo-endpoint removed and four method Route identities corrected. No active endpoint loss in that before/after comparison.
- Added docs/post-repair-optimization-review.md with priorities, evidence and acceptance criteria. Full suite now passes 173 total / 170 passed / three live skips; both business repositories remain clean.

## Repair completion 2026-09-05
- Finished all seven known regression fixes and the additional Windows MCP/Git pipe issue; full suite 148 tests, 145 passed and three opt-in live skips, zero failures.
- Remote policy v2 deployed after backup; six temporary-store tests pass, service active, policy permissions 600, versioned ETag and module hash verified. Production denials were not mutated for testing.
- Final installer version 0.3.1+codex.local-20260905-013149 is enabled. Fresh native stdio verifies 35 tools, TestPaper, save/search, DataFilter and actual v1-to-v2 lazy source-index migration. Remote HTTP discovery verifies 16 tools.
- Final sequential five-round baseline/repair medians: build 3.0146/3.3303s (+10.47%); hot-query batch 1.4769/1.0023s (−32.14%). Known line-comment pseudo-requests 17→0; maximum sampled payload 24,534 bytes.
- Retained the baseline first-build 40.215s outlier and installation-overlap run; final paired results and original baseline are in docs/optimization-repair-benchmark.json.
- Skill/plugin validators and installed source hashes pass. Both business repositories remain clean. CPM 0.3.1 retains its stale snapshot and three failures; no refresh or full DB load test ran.
- Delivered docs/optimization-repair-results.md. A fresh user thread remains the interactive handoff.
- Tool notes: a multi-file patch applied its source change before missing a progress heading; checked the partial state and patched only remaining documentation. A later combined documentation patch had a missing context prefix, was rejected, and was reapplied with valid context. Git pipe experiments used only temporary child processes.

- Repair release smoke check: fresh stdio discovery returns 35 tools, but Git inherited the Windows MCP input pipe and stalled during metadata reads. A temporary DEVNULL experiment isolated the cause; added two initially failing tests, detached Git stdin, and bounded each Git call to ten seconds with structured timeout status. Re-running installed-process verification and the five-round benchmark before final handoff.

## 2026-09-04
- Loaded the applicable GXP low-code debugging and file-planning skill instructions.
- Inspected current database repository, read-only session limits, MCP registration split, HTTP server, installer, and tests.
- Created persistent implementation plan and findings files.
- Added Schema snapshot configuration with secure policy-token storage and production URL validation.
- Added MySQL `information_schema` extraction, deterministic relationship candidate discovery, and aggregate-only full-data validation.
- Added the database-independent remote SQLite policy store, per-client token authentication, opaque rejection/restore API, audit trail, and operator CLI.
- Mounted policy routes beside the existing remote MCP without changing the remote MCP tool registry.
- Python compilation passed for the new policy modules. A system-Python smoke test exposed the expected missing project dependency; recorded for runtime-interpreter verification.
- Added the authenticated local policy client with ETag synchronization and immediate rejection-cache updates.
- Added the local 24-hour snapshot manager, atomic refresh, strict relation acceptance, policy fail-closed behavior, search/inspect APIs, and live non-persisted relation verification.
- Registered seven Schema/relation tools for local stdio only, preserved the remote MCP registry, and added cross-platform hidden-token configuration entrypoints.
- Added keyset pagination for tables, columns, indexes, constraints, and foreign-key rows so metadata sets beyond the 500-row session cap remain complete.
- Added focused tests for metadata-only candidate generation, strict aggregate validation, 501-column pagination, remote auth/ETag/roles/audit, shared rejection, lazy refresh, live fallback, and policy fail-closed behavior.
- First focused test run passed 15/16 tests; the sole Windows cleanup error was traced to an unclosed test-only SQLite connection and corrected.
- All new Python modules compile under the installed Look runtime; the first targeted unittest invocation exposed a missing `PYTHONPATH=mcp` test harness setting and was recorded.
- Updated the Skill routing contract, agent metadata, README, setup guide, user manual, CORS host/header configuration, and systemd persistent policy storage.
- Updated plugin discovery metadata so Schema and trusted-relation requests route to the expanded Skill behavior.
- Wired the configured per-query timeout into all metadata/validation sessions and added the bounded two-worker relationship validation pool with total refresh timeout handling.
- Completed CHECK pagination, Unicode-comment candidate terms, camel/underscore identifier matching, incoming declared-FK inspection, and target-key inference when callers omit target columns.
- Full regression ran 92 tests with 87 passing, 3 live tests skipped, and 2 prompt-contract failures; restored both required Skill prompt clauses.
- Added MCP tool descriptions and acceptance tests for HTTPS-only policy configuration, secret-field rejection, remote policy startup without database configuration, and atomic preservation after local refresh failure.
- Re-ran the complete suite: 96 tests passed with 3 opt-in live tests skipped; Python compilation and diff whitespace checks passed.
- Began final static review of timeout enforcement, remote opaque-data boundaries, ambiguity handling, and restore semantics.
- Added deadline-aware Schema queries, non-waiting executor shutdown, restore-time local relation invalidation, and ambiguity/restore regression tests; corrected one indentation error caught immediately by compileall.
- The 18-test Schema/policy focused suite now passes. Began remote deployment discovery; the provided literal SSH key path was not found on disk.
- Located the matching `code_new.pem` in a messaging download directory and the system OpenSSH executable; first connection was correctly rejected because the source key file's inherited ACL was too broad.
- Added the 8892 TLS reverse-proxy config and systemd allowed-host setting. The first combined backup/upload command had a shell quoting error, so remote state is being inspected before retrying with explicit paths.
- Reworked the policy design per user direction: JSON instead of SQLite, all endpoints authentication-free, fixed public URL/scope defaults, and no client-token configuration on new computers.
- Full local regression passes 99 tests with 3 opt-in live tests skipped. Uploaded the final JSON/public-policy files; the first remote preflight one-liner had quoting damage and is being retried with plain CLI arguments.
- Remote compilation passed and the temporary JSON scope was created. Application construction then identified three missing CPM import-support modules in the older server copy; these are being added without exposing CPM tools over HTTP.
- Installed the JSON policy systemd unit and 8892 Nginx configuration. Local policy health succeeded and the empty `gxp-development` scope was created; the combined verification stopped before public HTTPS because the socket check ran immediately after reload.
- Confirmed both sockets, healthy services, JSON mode, file mode 0600, and the empty scope over public HTTPS. The first inline Python MCP count check lost URL quotes in PowerShell and will be rerun over stdin.
- Final public verification passed: policy health and scope GET require no credentials, an unauthenticated invalid PUT reached relation-ID validation (400), and MCP negotiation returned exactly 16 remote tools with zero local Schema tools.
- Final full regression passed 99 tests with 3 opt-in live tests skipped; compileall and `git diff --check` passed. Remote JSON is mode 0600 and contains only the empty shared scope.
- Removed remote preflight JSON files. The executor blocked deletion of the ACL-restricted local temporary key copy after exact path validation, so it remains under the OS temp directory rather than using a shell bypass.
- A real first local development-DB refresh exercised the hard deadline and stopped at 300 seconds with no partial snapshot. Starting metadata/candidate-only timing to identify the bottleneck.
- Replaced per-table information-schema reads with six bulk keyset-paginated streams and replaced Cartesian candidate discovery with name/suffix indexes. Normalized legacy `ID_` as a generic key and de-duplicated identical relation endpoints.
- Real end-to-end refresh then succeeded in about 68 seconds: 915 tables, 23 declared foreign keys, 977 candidates, and 28 trusted data-verified relationships. All candidates were attempted; two database read timeouts were excluded and classified for next-day retry.
- Verified TTL behavior immediately afterward: the second access returned in 0.016 seconds with `refreshed=false`.
- Final regression after performance and timeout-classification changes: 101 tests passed, 3 opt-in live tests skipped; compileall and `git diff --check` passed.

## 2026-09-05
- Began a read-only audit of `F:\cpm\gxp2.web` and `F:\cpm\gxp2.components` to assess how the debugging Skill can locate source and reconstruct business flows more accurately.
- Restored the existing planning files. The prior versioned plugin-cache path is stale, so the active Skill path is being rediscovered before repository inspection.
- Read the complete active Skill, source-evidence rules and report contract; inspected the current source-hint generator, bounded `rg` searcher, registrations and synthetic tests.
- Confirmed both supplied repositories are clean `develop` checkouts and mapped their controller/service/DTO and component designer/runtime conventions without building or modifying either repository.
- Reproduced the stale default path failure, documentation-first component ranking, missing backend match for composed routes, and the plural `DataSetServices` source-hint failure.
- Traced representative real chains for `TestPaper`, `DataFilter`, `/api/datasets/search`, `/api/datasets/save`, field-schema extraction and dataset usage to define prioritized local-tool improvements.
- Completed the readonly audit; no frontend or backend business files were changed.
- Started converting the audit into a file-level implementation plan with tool contracts, confidence rules, tests and rollout gates.
- Added `docs/source-evidence-tools-implementation-plan.md`, covering dual F/G repository resolution, local-only source indexing, seven source/business-chain tools, evidence contracts, phased implementation, regression scenarios and completion gates.
- Started implementation from the approved source-evidence plan. Restored the planning, Skill update, and plugin update workflows; Phase 9 now covers the dual-path resolver and known search/hint regressions.
- Completed dual F/G/custom repository resolution, Git ambiguity handling, plural `Services` hints, Unicode-safe bounded search, runtime-role ranking, and cross-platform source configuration scripts.
- Added the metadata-only local source index with fingerprint freshness, locking, temporary builds and atomic replacement; the real F-drive repositories indexed in about 3.1 seconds (2,591 frontend files and 543 backend files).
- Registered all seven local source tools while keeping HTTP at 16 tools. Twenty-six focused parser/tool/registration tests pass; real `TestPaper`, datasets search/save, `DataSetServices` and DataFilter probes all produce source anchors.
- Completed structured component/API/backend/dataset/filter tools. Real API probes return one exact DataSet service implementation, three distinct `/api/datasets/save` callers, DTO contracts, and explicit `wrapper_unresolved` instead of claiming a body mismatch.
- Updated the Skill through progressive disclosure, source reference, setup guide, README, user manual and plugin metadata. Full regression passes 112 tests with 3 opt-in live tests skipped; official Skill and plugin validators pass.
- Added atomic partial-failure coverage, recursive DTO expansion, brace-bounded backend method edges, exception-flow anchors and fast dataset metadata lookup. Real tool responses are all below 64 KB.
- Installed the plugin through `scripts/install_codex_plugin.py`; `codex plugin list` reports the local marketplace plugin enabled, `cpm --version` is 0.3.1, and the installed source currently exposes 35 stdio tools versus 16 HTTP tools. Both business repositories remain clean.
- Final install uses cachebuster `0.3.1+codex.local-20260904-172829`; the installed `source_analysis.py` hash matches the repository. `cpm status` is operational but reports the pre-existing CPM snapshot stale with three prior failures; no platform refresh was triggered by this source-tool implementation.
- Review 2026-09-05 started: disambiguated committed control-flow/schema changes from the uncommitted source-tool implementation; full current unittest discovery ran 113 cases with 3 opt-in skips and zero failures. Independent adversarial probes are next.
- Independent review complete: docs/recent-optimizations-independent-review.md records separate verdicts for both latest commits and the uncommitted source work. docs/recent-optimizations-review-probes.py reproduces seven isolated failure categories. Real readonly source scans and golden-chain checks completed without rebuilding installed indexes. Final unittest rerun: 113 cases, 110 passed, 3 opt-in skips, zero failures; probe compilation and planning-file whitespace checks passed. No implementation fix or business-repository edit was made during this assessment.
- Repair baseline captured outside the repository. Five forced builds median 3.005s; five golden-query batches median 1.490s. Seven categories plus policy race tests were added first and failed on the old code. Policy/schema/fingerprint/operator fixes pass focused coverage; lexical frontend and typed backend are under real-repository/performance verification. Patch escaping and a renamed test fixture produced transient tool/test errors and were corrected.
