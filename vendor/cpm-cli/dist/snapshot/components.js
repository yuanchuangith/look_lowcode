import { extractTableProps } from './table-props.js';
/** 基础组件映射（与平台 AnalysisPageSchema.ts 一致，D:\code\test 实证 44 种） */
export const BASE_COMPONENTS_MAP = {
    EformInput: { title: '输入框', isForm: true },
    EformNumber: { title: '数字框', isForm: true },
    EformRichText: { title: '富文本框', isForm: true },
    EformButton: { title: '按钮', isForm: true },
    EformButtonGroup: { title: '按钮组', isForm: true },
    Tree: { title: '树形', isForm: true },
    EformSwitch: { title: '开关框', isForm: true },
    EformTextArea: { title: '文本框', isForm: true },
    EformText: { title: '文本', isForm: true },
    EformDatePicker: { title: '日期框', isForm: true },
    EformDateRangePicker: { title: '区间日期', isForm: true },
    EformHidden: { title: '隐藏域', isForm: false },
    EformStaticList: { title: '静态列表', isForm: true },
    EformDynamicList: { title: '动态列表', isForm: true },
    AssociatedRecordList: { title: '关联流程', isForm: true },
    EformMemberSelect: { title: '成员选择', isForm: true },
    SubTable: { title: '子表格', isForm: false },
    Table: { title: '表格', isForm: false },
    SelectFile: { title: '文件选择', isForm: true },
    SelectFolder: { title: '目录选择', isForm: true },
    Cascader: { title: '级联组件', isForm: true },
    Tag: { title: 'Tag标签', isForm: true },
    FileUpload: { title: '文件上传', isForm: true },
    ImgUpload: { title: '图片上传', isForm: true },
    EformImgUpload: { title: '图片上传', isForm: true },
    EformApplicationDept: { title: '申请部门', isForm: true },
    GxpLoadPage: { title: '页面引用', isForm: false },
    GxpCard: { title: '区块', isForm: false },
    'ConfigContainer.Item': { title: '配置项', isForm: true },
    FormTables: { title: '表格', isForm: true },
    GxpSmartTables: { title: '智能表格', isForm: true },
    ProcessButton: { title: '流程按钮', isForm: true },
    ProcessAuditMatrix: { title: '审核矩阵', isForm: true },
    DynamicFields: { title: '动态字段', isForm: true },
    ProgressGrid: { title: '进度平面图', isForm: true },
    FormTab: { title: '选项卡', isForm: true },
    FileUploadExt: { title: '文件上传扩展', isForm: true },
    AttachmentListExt: { title: '附件上传列表', isForm: true },
    OptionList: { title: '试题选项', isForm: true },
    TestPaper: { title: '试卷', isForm: true },
    FishBoneDiagram: { title: '鱼骨图', isForm: true },
    QRCode: { title: '二维码', isForm: true },
    GxpProcessCenter: { title: '流程中心', isForm: true },
    TreeTable: { title: '树表格', isForm: true },
    TreeSelect: { title: '下拉树表格', isForm: true },
    CardTables: { title: '卡片式表格', isForm: true },
};
/** 列配置类：提取 columnConfig 列/按钮 + 各处字典引用（EformDynamicList 列在 showconfig.allList，TestPaper 在 testStepSet） */
export const TABLE_TYPES = new Set(['FormTables', 'GxpSmartTables', 'TreeTable', 'CardTables', 'Table', 'SubTable', 'EformDynamicList', 'TestPaper']);
/** 单值字段类：运行时 inbiz('id').value 有意义（D:\code\test 实证 26 种） */
export const VALUE_COMPONENT_TYPES = new Set([
    'EformInput', 'EformNumber', 'EformRichText', 'EformSwitch',
    'EformTextArea', 'EformText', 'EformDatePicker', 'EformDateRangePicker',
    'EformStaticList', 'EformDynamicList', 'EformMemberSelect',
    'SelectFile', 'SelectFolder', 'AssociatedRecordList',
    'Cascader', 'Tag',
    'FileUpload', 'ImgUpload', 'EformImgUpload',
    'EformApplicationDept', 'FileUploadExt', 'AttachmentListExt',
    'DynamicFields', 'ProcessAuditMatrix', 'TreeSelect',
]);
// ── 绑定提取（kind 分派规则移植自 D:\code\test 各组件 binding.ts）──
/** dataCenter/querySet 解析：真实 schema 中可能是对象或 JSON 字符串，两者都兼容 */
function parseCenter(v) {
    if (!v)
        return undefined;
    if (typeof v === 'string') {
        try {
            return JSON.parse(v);
        }
        catch {
            return undefined;
        }
    }
    return typeof v === 'object' ? v : undefined;
}
const valid = (v) => v !== undefined && v !== null && v !== '';
/** dataSet 绑定：dataCenter 优先，裸 modelkey 兜底（两者语义均为数据集 id） */
function dataSetBinding(props) {
    const dc = parseCenter(props.dataCenter);
    const dataSetId = valid(dc?.value) ? String(dc?.value) : (valid(props.modelkey) ? String(props.modelkey) : undefined);
    const modelName = valid(dc?.modelname) ? String(dc?.modelname) : (valid(props.modelname) ? String(props.modelname) : undefined);
    if (!dataSetId && !modelName)
        return undefined;
    return clean({ kind: 'dataSet', dataSetId, modelName, primaryKey: dc?.primaryKey, sourceType: dc?.sourcetype });
}
/** switchable 绑定（Tree 用 querySet，其余用 dataCenter）：modelKey 语义保留 */
function switchableBinding(props, centerKey) {
    const dc = parseCenter(props[centerKey]);
    const modelKey = valid(dc?.value) ? String(dc?.value) : (valid(props.modelkey) ? String(props.modelkey) : undefined);
    if (!modelKey)
        return undefined;
    return clean({
        kind: 'switchable', modelKey,
        modelName: dc?.modelname ?? props.modelname,
        primaryKey: dc?.primaryKey, sourceType: dc?.sourcetype ?? props.sourcetype,
        ...(valid(props.sourceModel) ? { sourceModel: String(props.sourceModel) } : {}),
    });
}
/** childModel 绑定：childModelConfig 开启才有（成员选择/级联/上传扩展等） */
function childModelBinding(props) {
    if (!props.childModelConfig)
        return undefined;
    const business = props.storageConfig?.business;
    return clean({ kind: 'childModel', childModel: { enabled: true, ...(valid(business) ? { business } : {}) } });
}
function clean(b) {
    const out = { kind: b.kind };
    let has = false;
    for (const [k, v] of Object.entries(b)) {
        if (k === 'kind' || k === 'childModel')
            continue;
        if (valid(v)) {
            out[k] = v;
            has = true;
        }
    }
    if (b.childModel) {
        out.childModel = b.childModel;
        has = true;
    }
    return has ? out : undefined;
}
/** 按组件类型分派绑定提取（分派表 = D:\code\test 各 binding.ts 的 kind 分布） */
function bindingOf(componentType, node) {
    const p = node['x-component-props'] ?? {};
    switch (componentType) {
        case 'FormTables':
        case 'GxpSmartTables':
        case 'TreeTable':
        case 'EformDynamicList':
            return dataSetBinding(p);
        case 'EformStaticList': {
            // 字典 id 三形态：组件级 dictId/dictionaryKey，或列式 format.relatedDictionary（实测 CAPA列表）
            const dictId = p.dictId ?? p.dictionaryKey
                ?? (p.format?.type === 'staticList' ? p.format?.relatedDictionary : undefined);
            return valid(dictId) ? clean({ kind: 'dict', dictId: String(dictId) }) : undefined;
        }
        case 'EformMemberSelect':
        case 'Cascader':
        case 'FileUploadExt':
        case 'Transfer':
            return childModelBinding(p);
        case 'Tree':
            return switchableBinding(p, 'querySet');
        case 'TreeSelect':
        case 'Tag':
        case 'AttachmentListExt':
            return switchableBinding(p, 'dataCenter');
        default:
            return undefined;
    }
}
// ── 引用对象构造（格式对齐平台 ParamInput.tsx，不自拼变体）──
function componentRef(id, title, type) {
    return { paramTypes: 'componentsVariable', value: `componentsVariable-${id}`, label: `页面组件-${title}`, dataType: type, code: `inbiz('${id}')` };
}
function componentValueRef(id, title, type) {
    return { paramTypes: 'componentsVariable', value: `${id}-value`, label: `页面组件-${title}-当前值`, dataType: type, code: `inbiz('${id}').value` };
}
/** 递归压平组件清单：白名单外跳过；表格类提取列/按钮 */
function parseComponentList(properties, result, stats) {
    for (const [key, node] of Object.entries(properties)) {
        const n = node;
        const componentType = n['x-component'] || '';
        const matched = BASE_COMPONENTS_MAP[componentType];
        if (matched) {
            const props = n['x-component-props'] ?? {};
            const title = props.cardTitle || n.title?.value || key;
            const info = {
                id: key, title: String(title),
                componentType, componentName: matched.title, isForm: matched.isForm,
                ref: componentRef(key, String(title), componentType),
            };
            if (VALUE_COMPONENT_TYPES.has(componentType))
                info.valueRef = componentValueRef(key, String(title), componentType);
            const binding = bindingOf(componentType, n);
            if (binding)
                info.binding = binding;
            if (TABLE_TYPES.has(componentType))
                extractTableProps(props, info);
            if (n.properties)
                stats.containers++;
            else
                stats.fields++;
            result.push(info);
        }
        if (n.properties)
            parseComponentList(n.properties, result, stats);
    }
}
/**
 * 页面结构总入口。入参为 getPageSchema 原始响应（page.json 内容）；
 * 主模型取 content.form.model（页面级唯一模型绑定，实测）。
 */
export function buildPageComponents(pageSchema) {
    const s = pageSchema;
    const schemaRoot = s?.content?.schema ?? s;
    const model = s?.content?.form?.model;
    const componentList = [];
    const stats = { containers: 0, fields: 0 };
    if (schemaRoot?.properties)
        parseComponentList(schemaRoot.properties, componentList, stats);
    return {
        modelInfo: valid(model?.ModelKey)
            ? { ModelKey: String(model.ModelKey), Name: String(model.Name ?? ''), Describe: model.Describe, ModelType: model.ModelType }
            : null,
        componentList,
        stats,
    };
}
/** 模型字段查找辅助：AI 核对 Schema 字段路径时用（columns 项 PascalCase） */
export function findColumn(columns, name) {
    return columns?.find(c => c.Name === name || c.OldName === name);
}
//# sourceMappingURL=components.js.map