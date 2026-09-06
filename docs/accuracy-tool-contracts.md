# Accuracy tool extensions

All changes are read-only. Existing tool names and the 35-local/16-HTTP registration split remain unchanged. New inputs are optional. Remote deployment is not part of this update.

## Conversation routing

`diagnose_codex_input(text, at_time?, context?)` accepts the current thread's goal, anchors, rules, exclusions, field_meanings, chosen_approach, findings and corrections. Maximum context size is 32 KiB, maximum eight anchors. Nothing is persisted. Returned context is explicitly user-supplied, not database evidence. Explicit current action identity wins over old anchors; recheck requests return compare_designs/inspect_action with current-design guidance. JSON CLI input accepts `context` too.

## Canvas reads and field references

Group selection uses exact key, then unique exact title, then unique fuzzy match. Ambiguity returns candidates, not arbitrarily merged groups. `focus_fields` additionally matches condition operands, variable values, assignments, loops and return references. References include expression, role, source path, scope and confidence; lexical coverage is partial and zero hits do not prove non-use. Individual expressions over 128 KiB are not lexically expanded; at most64 distinct references per expression are retained.

Local calls retain `actionName.value` as target_group_key, distinguish public/local calls and report resolution status. Public targets remain exact identifiers. Generated code lookup attempts an exact group-key method using lexical method boundaries, caches eight source snapshots in-process, and retains whole-action candidate fallback when the method is ambiguous/unknown. This is not a compiler source map.

`inspect_action` adds max_output_bytes (default32768, range8192..65536), value_path, value_offset and value_limit (default2048, range1..8192). value_path is a JSON pointer restricted to one node's /paramsValue. Paging needs group and node_key; continuation also needs design_id. Offsets count Unicode characters of text, or the JSON representation for non-string values. Returned next_read keeps the exact design. Large characters may reduce the returned chunk below value_limit.

Large responses preserve identity/version and explicitly mark missing evidence. Read next_read and omitted entries before a definitive judgment. Array-count truncation and byte-budget truncation are distinct. The budget measures UTF-8 JSON with indent2, not transport framing.

## Call and field flow

`inspect_control_flow` adds follow_calls=false, max_call_depth=2 (maximum5), max_actions=8 (maximum8), and max_output_bytes. Existing max_nodes/max_edges also bound expanded flow. The optional call_flow uses action/design/group-qualified identities, explicit argument, return, loop and write relationships, and branch-path annotations. Edges are static relations, never runtime coverage or verified foreign keys.

The selected group is the entry; absent group uses an unambiguous main. Dynamic targets, unavailable parameter contracts, missing-argument candidates, recursion and limits are explicit unresolved items. Multiple call sites retain separate binding edges. Root snapshot version controls callee selection; historical expansion is published-only and uses the requested time or a deleted published root's timestamp. No table records, SQL scans, or source repository refreshes are used by this expansion.

CLI equivalents: inspect_action.py --control-flow --follow-calls --max-call-depth 2 --max-actions 8; regular reads support --max-output-bytes, --design-id, --at-time, --value-path, --value-offset and --value-limit.

## Knowledge discovery

`get_cpm_knowledge(kind="catalog", name="main", query="变量", limit=20)` lists only existing allow-listed topics. The maximum limit is100. Variable/array/assignment queries suggest actual variable elements and language guidance. Entries contain next_call arguments. Existing topic reads remain supported. `scripts/inspect_knowledge.py` exposes the same options locally; path traversal stays rejected.

## Verification boundary

Automated synthetic regression and fixed-evidence paired model replay do not equal live platform success. The replay records batch latency, tool calls, output bytes and model decisions for twelve scenarios. No percentage improvement across general real conversations is inferred from this small set.
