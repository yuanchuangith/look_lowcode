// page.schema 的查询字段定义剥离（2026-08-26 实测普查 433 页）：
// dataCenter.queryField（589 处）/ columnConfig.queryFields（425 处）及其同类尾巴
// （xxxSet / tableListConfig / expandTableConfig，63 处）合计约 6.8MB（pages 目录 13%），
// 与 columnConfig.properties 列定义高度重复，属可从列配置推导的干扰数据。
// 注意：其中的字典引用（relatedDictionary）是 bindings.md 字典段 / components.json
// dictIds 的来源——必须在衍生文件生成之后调用（writer.writePages 顺序保证），信息零损失。
// 原地修改（管线内部数据，无共享引用）；非对象入参安全跳过。
/** 递归删除对象树中所有 queryField / queryFields 键（原地） */
export function stripQueryFields(root) {
    if (!root || typeof root !== 'object')
        return;
    if (Array.isArray(root)) {
        for (const item of root)
            stripQueryFields(item);
        return;
    }
    const obj = root;
    delete obj.queryField;
    delete obj.queryFields;
    for (const v of Object.values(obj))
        stripQueryFields(v);
}
