# Task Plan: Local Schema Snapshot and Trusted Relations

## Goal
Implement a local daily MySQL schema snapshot with data-verified logical relations, a remote opaque rejection-policy service, local MCP tools, configuration/install integration, documentation, and tests.

## Decisions
- Schema and relation details stay local; remote stores only opaque relation IDs and audit metadata.
- Logical relations require target uniqueness, compatible types, at least 20 distinct non-null source keys, and 100% full-data match.
- User rejection is permanent and shared per policy scope until explicitly restored.
- Refresh is lazy on first access after a 24-hour TTL.
- Policy is checked before inferred relations are used; policy outage fails closed for inferred relations.
- Remote MCP tool set remains unchanged; new schema/relation tools are local stdio only.

## Phases
1. [complete] Baseline architecture and contracts
2. [complete] Local schema snapshot, candidate generation, and live verification
3. [complete] Remote JSON policy persistence and client integration
4. [complete] MCP tools, configuration scripts, Skill, docs, and installer integration
5. [complete] Unit/integration tests, remote deployment, and full verification

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| System Python could not import `pymysql` while smoke-testing the policy store because `gxp_core.__init__` eagerly imports the service | 1 | Use the installed Look runtime Python for repository tests; policy code itself has no database connection or configuration dependency. |
| Direct `unittest tests.test_server_tools` did not find `server` | 1 | Repository tests require `mcp` on `PYTHONPATH`; rerun with the established test import path. |
| Windows could not remove a test SQLite file | 1 | The test used SQLite's transaction context without closing the connection; close it explicitly before temporary-directory cleanup. |
| Combined documentation patch missed the intended Skill insertion context | 1 | Split the change into small file-specific patches and insert the new section directly before the existing business-rule heading. |
| Plugin metadata patch used decoded Chinese while the JSON stores Unicode escapes | 1 | Patch the ASCII description separately and leave the already-updated Skill agent metadata as the user-facing routing source. |
| Full suite found two Skill prompt contract regressions | 1 | Restore the required compact-read and editor-boundary phrases while retaining the new Schema routing text. |
| Deadline patch placed the existing `raise` outside `ReadOnlySession.__enter__`'s exception block | 1 | Restored the exception cleanup indentation and kept `set_query_timeout` as a separate method. |
| SSH key path `F:\\Desktop\\code\\_new\\.pem` was not present and its parent lookup returned no entries | 1 | Inspect nearby explicit desktop paths for the intended PEM filename before attempting SSH again. |
| OpenSSH rejected the discovered `code_new.pem` because inherited ACLs exposed it to another local group | 1 | Use a temporary deployment-only copy with inheritance removed and read permission limited to the current Windows identity. |
| First remote backup command mixed PowerShell interpolation with Bash variables and produced an unmatched-quote error | 1 | Use a timestamp computed locally and fully explicit remote paths; inspect whether subsequent SCP transfers completed before continuing. |
| Remote preflight embedded Python command lost quote escaping through PowerShell/SSH | 1 | Use the deployed management CLI with plain arguments and a separate simple import command instead of nested Python string literals. |
| Second preflight print literal was also damaged by nested SSH quoting | 2 | Remove the unnecessary print call entirely from the import check. |
| Remote application import found missing `gxp_core.cpm_snapshot` after the new server registry was uploaded | 1 | Upload the three local-only CPM support modules required at import time; HTTP still registers none of their tools. |
| First post-restart health probe hit the brief startup window, then succeeded on retry; the combined check stopped because `ss` had not yet shown 8892 immediately after Nginx reload | 1 | Inspect Nginx loaded configuration, service journal, sockets, and HTTPS separately before changing configuration.
| PowerShell native `python -c` removed quotes from the inline remote MCP URL | 1 | Pipe the verification source to Python stdin so URL quoting is preserved.
| Combined remote and local temporary-file cleanup was rejected by the command safety layer | 1 | Separate remote cleanup over SSH from locally validated native PowerShell cleanup.
| The first explicit local cleanup path used `C:` while this environment's temp root is on `F:`; subsequent `Remove-Item` remained blocked by the executor even after exact-path validation | 2 | Remote preflight files were removed. The temporary key copy remains ACL-restricted in the OS temp directory; no further shell bypass was attempted.
| First real development-database refresh reached the 300-second deadline and preserved the empty/old snapshot state | 1 | Measure metadata-load duration and candidate count without data validation, then optimize the validation workload while retaining the fixed deadline.
