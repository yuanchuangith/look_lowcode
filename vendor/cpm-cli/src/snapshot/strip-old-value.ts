// page.schema 的编辑器历史快照剥离（2026-08-26 实测）：
// 平台把组件 dataCenter 的历史值链 oldValue.oldValue…（最深 14 层，每层复制完整
// queryField 数组）序列化进 schema——284/433 页携带，平均占 page.json 体积 54%，
// 属纯编辑器快照噪声（不是有效配置）。落盘前剥离；组件树/绑定收集不读该链，行为不变。
// 原地修改（管线内部数据，无共享引用）；非对象入参安全跳过。
/** 递归删除对象树中所有 oldValue 键（原地） */
export function stripOldValue(root) {
    if (!root || typeof root !== 'object')
        return;
    if (Array.isArray(root)) {
        for (const item of root)
            stripOldValue(item);
        return;
    }
    const obj = root;
    delete obj.oldValue;
    for (const v of Object.values(obj))
        stripOldValue(v);
}
