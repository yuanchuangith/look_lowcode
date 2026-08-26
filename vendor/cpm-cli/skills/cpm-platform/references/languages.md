# 多语言（languages/）详解

平台多语言词条全量（1477 条 × 4 语种），是菜单名/页面名/导航名/组件 title 中 `{multilingual}` 占位的**翻译查询处**。

## 文件形态

| 文件 | 内容 |
|------|------|
| `zh-cn.json` / `en.json` / `ja.json` / `zh-hant.json` | 该语种的 `key → 文本` 映射（4 文件 key 集合一致） |
| `kinds.json` | 语种字典：`Id/Name/Code/IsDefault/IsSystem/IsShow/Sort`（zh-cn 为默认语种） |

key 规则：词条占位符 `{multilingual}global.i18n-xxx` 剥掉 `{multilingual}global.` 前缀后的裸 key（本快照占位**全部**是 `global.` 前缀）。

## 查询路径（占位 → 人话）

1. 在菜单/页面/导航/组件 `title.value` 里看到 `{multilingual}global.i18n-jq65smcr`
2. 剥前缀得 key：`i18n-jq65smcr`
3. 查 `zh-cn.json`：`"i18n-jq65smcr": "离岗原因"` → 显示名即「离岗原因」；其它语种查对应文件
4. key 查不到 = 平台侧词条缺失（bindings.md 的「⚠ i18n 缺失 key」节即此类问题）

注意：`components.json` 的 `title` 已优先解析为最终显示名（cardTitle > title.value > key 回退），多数场景无需手动查翻译；本文件用于菜单/导航名与缺失场景核对。

## 语种覆盖

快照中的资源目录/文件名（`中文名-短码`）与字典选项文本已是最终中文；菜单名、导航名、页面名、组件 `title.value` 则可能仍是 `{multilingual}` 占位，需要时按上述路径翻译。
