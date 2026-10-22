# 请求内读取复用

每次 MCP 调用仍创建独立的 `GxpReadonlyService` 和 `GxpRepository`，不跨请求缓存动作身份或草稿内容。

- 已按 code 或 RefId 查询的目录记录，按明确的 `ref_id` 保存本次请求的元数据副本。随后 `load_design` 组装动作身份时复用该副本，省去重复目录查询。名称搜索命中记录也可复用元数据，搜索标记不进入动作身份。
- 身份索引不会把查询过的 code 自动当作其他字符串查询的完整结果。code 与其他动作 RefId 重名时，`resolve_action` 仍查询并保留全部候选，不因缓存漏掉歧义。
- `inspect_action` 默认只读取画布 JSON；未指定 `include_generated_csharp` 或 `csharp_line` 时，查询不传输完整生成 C#。数据库按完整 C# 文本的 UTF-8 字节计算 SHA-256，响应仍提供 `csharp_sha256`。请求 C# 搜索或定位行号时仍读取完整代码。
- `GxpRepository.load_design(..., include_csharp=True)` 默认行为保持兼容。新参数为内部按需读取入口，不改变 MCP 工具参数。缺失的数据库指纹会明确报错，不以空代码指纹代替。

验证覆盖请求内少查一次目录、请求间身份刷新、code/RefId 交叉歧义、中文及非 BMP 字符的完整内容指纹、默认画布查询和显式 C# 查询路径。不连接业务数据库、不安装插件。
