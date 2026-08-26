/** 表单字段引用对象（格式对齐平台 ParamInput.tsx）*/
export function formDataFieldRef(attr, title, dbType) {
    return { paramTypes: 'formDataVariable', value: `formDataVariable-${attr}`, label: `表单字段-${title}`, dataType: dbType || 'string', code: `relatedAttributes.GetFormData('${attr}')` };
}
/** 列的字典 id：format.type=staticList 且 relatedDictionary 合法才返回 */
function columnDictId(col) {
    const f = col.format;
    if (f && typeof f === 'object' && f.type === 'staticList'
        && typeof f.relatedDictionary === 'string' && f.relatedDictionary) {
        return f.relatedDictionary;
    }
    return undefined;
}
/** 查询字段/展示列数组的字典引用收集进共享 Set（queryFields / queryField / allList 同形态） */
function collectColumnDicts(list, dictIds) {
    if (!Array.isArray(list))
        return;
    for (const col of list) {
        const dictId = col && columnDictId(col);
        if (dictId)
            dictIds.add(dictId);
    }
}
/** 表格列/按钮提取：按钮（operation）+ 数据列（properties）+ 查询/展示列字典（queryFields/queryField/allList） */
export function extractTableProps(props, info) {
    const columnConfig = props.columnConfig ?? {};
    const operation = columnConfig.operation ?? [];
    if (Array.isArray(operation) && operation.length > 0) {
        info.buttons = operation.map((op) => ({ id: op.id, title: op.title, type: op.type, position: op.position }));
    }
    const colProps = columnConfig.properties;
    const dictIds = new Set();
    // 字典引用四处（真机 2026-08-26 普查）：表格 columnConfig.queryFields、
    // 字段级 dataCenter.queryField、EformDynamicList 选择窗 showconfig.allList、
    // TestPaper 试卷步骤 testStepSet.queryField
    collectColumnDicts(columnConfig.queryFields, dictIds);
    collectColumnDicts(props.dataCenter?.queryField, dictIds);
    collectColumnDicts(props.showconfig?.allList, dictIds);
    collectColumnDicts(props.testStepSet?.queryField, dictIds);
    if (Array.isArray(colProps) && colProps.length > 0) {
        const columns = colProps
            .filter((col) => col && col.attributeName)
            .map((col) => {
            const attributeName = String(col.attributeName);
            const title = String(col.title || attributeName);
            const dictId = columnDictId(col);
            if (dictId)
                dictIds.add(dictId);
            return {
                attributeName, title, dbType: col.dbType, visible: col.visible,
                ...(dictId ? { dictId } : {}), // 列级字典（components.json 机器可读）
                ref: formDataFieldRef(attributeName, title, col.dbType),
            };
        });
        if (columns.length > 0)
            info.columns = columns;
    }
    if (dictIds.size > 0)
        info.dictIds = [...dictIds]; // 组件级字典引用全集（各来源，去重）
}
//# sourceMappingURL=table-props.js.map