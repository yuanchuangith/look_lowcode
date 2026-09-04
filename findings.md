# Findings

- Existing `describe_table` returns only `DESCRIBE` and `SHOW INDEX`; it omits table/column comments and cross-table relationships.
- Existing read-only session enforces `START TRANSACTION READ ONLY`, a 10-second maximum execution time, and a 500-row result cap.
- Existing CPM refresh manager provides cross-platform file locks, temporary work directories, status files, and atomic directory replacement suitable for reuse.
- Local stdio currently registers 21 tools (16 shared database tools plus 5 local CPM tools); HTTP registers only the 16 shared tools.
- Remote HTTP service is a Starlette/FastMCP application and currently has no policy persistence or authentication.
- Python requirements have no HTTP client dependency; standard-library `urllib` and `sqlite3` can implement the policy client/server without adding a package.
- Database is MySQL-compatible through PyMySQL. Schema metadata should come from `information_schema` and must be paginated below the session result cap.
- Remote policy can live beside the existing MCP ASGI app while keeping database-dependent Schema tools local-only.
- A stable per-database `policy_scope_id` plus SHA-256 over normalized endpoints lets the remote service enforce shared rejections without receiving table or column names.
- Strict verified relationships can be represented as a binary state rather than a probabilistic score; ambiguous or under-populated candidates stay outside the trusted graph.
- The deployed systemd service uses `ProtectSystem=strict`; `StateDirectory=gxp-lowcode-readonly` plus an explicit `GXP_RELATION_POLICY_DB` path is required for writable remote policy persistence.
- Policy HTTPS deployments may use a reverse-proxy Host, so the HTTP service accepts explicit additional hosts through `GXP_LOWCODE_HTTP_ALLOWED_HOSTS` while retaining the fixed defaults.
- Full regression after the latest acceptance tests passes 96 tests (3 opt-in live tests skipped); compileall and `git diff --check` also pass.
- Static review found two acceptance gaps to close: restoring a rejected relation currently exposes the old verified snapshot without revalidation, and the validation executor context can wait beyond the refresh deadline for running futures.
- User simplified the remote policy contract: persistence is now a small atomically replaced JSON file and all policy endpoints are authentication-free. The built-in public endpoint/scope lets a newly installed Skill synchronize without moving a token.
- Production endpoint `https://43-135-137-212.sslip.io:8892` is live through Nginx TLS. Policy health reports JSON storage, `gxp-development` is revision 0 with no rejections, and the remote MCP registry remains 16 tools with no local Schema tools.
- The real development database contains 915 tables and 15,640 columns. Bulk metadata paging completes in about 8-14 seconds; indexed candidate discovery replaces the original table Cartesian scan.
- The successful first snapshot evaluated all 977 conservative candidates in about 68 seconds: 28 data-verified relations, 878 insufficient-data candidates, 69 orphan/unmatched candidates, and 2 read timeouts. Timeout candidates stay out of the graph and are prioritized on the next refresh.
