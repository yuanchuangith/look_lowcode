import { buildPageComponents } from './components.js';
import { extractTitle } from './tree-md.js';
const INBIZ_RE = /inbiz\(['"]([^'"]+)['"]\)/g;
/** 事件订阅静态提取：action.js 中 relatedAttributes.eventson('<事件Key>', fn)（2026-08-26 本地考古：
 *  平台 BizFlow 列表 event 字段实测全空、设计响应无映射；真实订阅形态在编译后的规则代码里） */
const EVENTSON_RE = /eventson\(\s*['"]([^'"]+)['"]/g;
export function extractEventSubs(flows) {
    const subs = [];
    for (const f of flows) {
        const js = f.codes?.js ?? '';
        EVENTSON_RE.lastIndex = 0;
        let m;
        while ((m = EVENTSON_RE.exec(js)) !== null) {
            subs.push({ eventCode: m[1], ruleCode: f.code, ruleName: f.describe || f.code });
        }
    }
    return subs;
}
/** 从任意文本提取 inbiz('xxx') 引用 */
function extractInbizRefs(text) {
    const out = [];
    let m;
    INBIZ_RE.lastIndex = 0;
    while ((m = INBIZ_RE.exec(text)) !== null)
        out.push(m[1]);
    return out;
}
/** 布局/容器家族：无子节点时也不是模型字段（实测空 GridColumn、RightExtraContent 会混进字段表） */
const LAYOUT_TYPES = new Set([
    'FormGrid', 'FormGrid.GridColumn',
    'FormTab', 'FormTab.TabPane', 'FormTab.RightExtraContent', 'FormTab.LeftExtraContent',
    'GxpCard', 'GxpLoadPage', 'ConfigContainer', 'ConfigContainer.Item',
]);
/** Schema 递归收集组件 ref、展示信息与叶子字段（name 即字段路径） */
function scanSchema(node, acc) {
    const name = typeof node.name === 'string' && node.name ? node.name : '';
    const componentType = typeof node['x-component'] === 'string' ? node['x-component'] : '';
    if (name) {
        acc.componentRefs.push(name);
        const title = componentType ? extractTitle(node) : '';
        if (componentType)
            acc.componentInfos.push({ name, componentType, title });
        const isContainer = node.properties && Object.keys(node.properties).length > 0;
        if (componentType && !isContainer && !LAYOUT_TYPES.has(componentType)) {
            // 模型字段判定：平台在 x-component-props.model 显式存了绑定列元数据
            // （Name=真实列名如 applicant_id；实测 56/56 命中且纠正名字推断的错位）
            const model = node['x-component-props']?.model;
            const info = {
                name, componentType, title,
                ...(typeof model?.Name === 'string' && model.Name
                    ? { columnName: model.Name, ...(model.Type ? { columnType: String(model.Type) } : {}) }
                    : {}),
            };
            if (info.columnName)
                acc.fields.push(info);
            else
                acc.unboundComponents.push(info);
        }
    }
    for (const child of Object.values(node.properties ?? {})) {
        scanSchema(child, acc);
    }
}
export function collectBindings(input) {
    const comps = buildPageComponents(input.pageSchema);
    const datasets = [];
    const dictionaries = [];
    const childModels = [];
    const switchables = [];
    for (const c of comps.componentList) {
        if (c.binding?.kind === 'dataSet') {
            datasets.push({ dataSetId: c.binding.dataSetId, modelName: c.binding.modelName, component: c.id });
        }
        else if (c.binding?.kind === 'dict') {
            dictionaries.push({ dictId: c.binding.dictId, component: c.id });
        }
        else if (c.binding?.kind === 'childModel') {
            childModels.push({ component: c.id, business: c.binding.childModel?.business });
        }
        else if (c.binding) {
            switchables.push({ modelKey: c.binding.modelKey, modelName: c.binding.modelName, component: c.id });
        }
        // 列级字典：一个组件可引用多个字典（实测形态 format.relatedDictionary）
        for (const id of c.dictIds ?? [])
            dictionaries.push({ dictId: id, component: c.id });
    }
    const scanAcc = {
        componentRefs: [],
        componentInfos: [],
        fields: [],
        unboundComponents: [],
    };
    const s = input.pageSchema;
    const schemaRoot = s?.content?.schema ?? s;
    if (schemaRoot && typeof schemaRoot === 'object')
        scanSchema(schemaRoot, scanAcc);
    // 代码引用：js/cs 代码 + 规则 action 原串（实测为 ID 槽位，统一扫描无害）
    const allCode = [];
    for (const c of input.codes) {
        if (c.js)
            allCode.push(c.js);
        if (c.cs)
            allCode.push(c.cs);
    }
    for (const f of input.flows)
        allCode.push(String(f.action ?? ''));
    const codeRefs = [...new Set(allCode.flatMap(extractInbizRefs))];
    // 公共编排引用：页面代码中出现其 code 或 name 即命中（保留名称对象供渲染双写）
    const codeText = allCode.join('\n');
    const publicBizflows = input.publicBizflowCodes
        .filter(pf => codeText.includes(pf.code) || (pf.name ? codeText.includes(pf.name) : false))
        .map(pf => ({ code: pf.code, name: pf.name }));
    const m = comps.modelInfo;
    // 子表组件无 model.Name 但绑数据集（数据集节已列）→ 不算「无绑定页面组件」
    const datasetComps = new Set(datasets.map(d => d.component));
    return {
        mainModel: m ? { modelKey: m.ModelKey, name: m.Name, describe: m.Describe } : null,
        datasets, dictionaries, dictNames: input.dictNames, childModels, switchables,
        processFlows: input.processFlows ?? [],
        fields: scanAcc.fields,
        unboundComponents: scanAcc.unboundComponents.filter(f => !datasetComps.has(f.name)),
        componentInfos: scanAcc.componentInfos,
        componentRefs: scanAcc.componentRefs,
        codeRefs, publicBizflows,
        brokenI18nKeys: input.brokenI18nKeys,
    };
}
function section(title, items) {
    const body = items.length > 0 ? items.map(x => `- ${x}`) : ['- （未检测到）'];
    return [`## ${title}`, ...body, ''];
}
/** 同组件同字典去重（列级收集可能产生重复：多列引用同一字典） */
function dedupeDicts(dicts) {
    const seen = new Set();
    return dicts.filter(d => {
        const k = `${d.component}+${d.dictId}`;
        if (seen.has(k))
            return false;
        seen.add(k);
        return true;
    });
}
/** 组件行内双写：name (Type) title；信息缺失时逐段缩短（AI 单行可读，免跳 tree.md） */
function fmtComp(name, infoByName) {
    const info = infoByName.get(name);
    if (!info)
        return name;
    const type = info.componentType ? ` (${info.componentType})` : '';
    return `${name}${type}${info.title ? ` ${info.title}` : ''}`;
}
/** 字段/代码引用行渲染：name (Type) title；withColumn 时附加显式模型列绑定 */
function fmtInfo(f, withColumn = false) {
    const type = f.componentType ? ` (${f.componentType})` : '';
    const base = `${f.name}${type}${f.title ? ` ${f.title}` : ''}`;
    if (!withColumn || !f.columnName)
        return base;
    return `${base} → ${f.columnName}${f.columnType ? `（${f.columnType}）` : ''}`;
}
/** 字典行渲染（按字典聚合）：名称优先（id 括注）→ 组件（title 括注）；无映射时裸 id（保持 AI 可检索） */
function dictLines(b, infoByName) {
    const byDict = new Map();
    for (const d of dedupeDicts(b.dictionaries)) {
        const comps = byDict.get(d.dictId) ?? [];
        if (!comps.includes(d.component))
            comps.push(d.component);
        byDict.set(d.dictId, comps);
    }
    return [...byDict.entries()].map(([dictId, comps]) => {
        const name = b.dictNames?.get(dictId);
        const head = name ? `${name}（${dictId}）` : dictId;
        const compStr = comps
            .map(c => infoByName.get(c)?.title ? `${c}（${infoByName.get(c).title}）` : c)
            .join('、');
        return `${head} → ${compStr}`;
    });
}
export function renderBindingsMd(route, b) {
    const infoByName = new Map(b.componentInfos.map(i => [i.name, i]));
    const refSet = new Set(b.componentRefs);
    const dangling = b.codeRefs.filter(r => !refSet.has(r)).map(r => `⚠ ${r}（页面 Schema 无此组件，疑似失效引用）`);
    const valid = b.codeRefs
        .map(r => infoByName.get(r) ?? { name: r, componentType: '', title: '' })
        .map(i => fmtInfo(i));
    const lines = [
        `# ${route} 绑定清单`,
        '',
        ...section('主模型（form.model）', b.mainModel
            ? [`${b.mainModel.name}（${b.mainModel.modelKey}）${b.mainModel.describe ? `— ${b.mainModel.describe}` : ''}`]
            : []),
        ...section('数据集（组件 → 数据集）', b.datasets.map(d => `${fmtComp(d.component, infoByName)} → ${d.dataSetId ?? '?'}${d.modelName ? `（${d.modelName}）` : ''}`)),
        ...section('字典（字典 → 组件）', dictLines(b, infoByName)),
        ...section('子模型存储（childModelConfig）', b.childModels.map(c => `${fmtComp(c.component, infoByName)}${c.business ? ` → ${c.business}` : ''}`)),
        ...section('可切换数据源（树类组件）', b.switchables.map(s => `${fmtComp(s.component, infoByName)} → ${s.modelKey ?? '?'}${s.modelName ? `（${s.modelName}）` : ''}`)),
        ...section('模型字段（字段 → 组件 → 模型列）', b.fields.map(f => fmtInfo(f, true))),
        ...section('页面组件（无模型列绑定；纯前端控件）', b.unboundComponents.map(f => fmtInfo(f))),
        ...section('审批流程（以本页为表单的 BPMN 工作流）', b.processFlows.map(f => `${f.name}（v${f.version ?? '-'}）→ ${f.dir}；链路读 process.xml，节点审批人读 ext.json`)),
        ...section('公共编排', b.publicBizflows.map(p => (p.name ? `${p.name}（${p.code}）` : p.code))),
        ...section('代码引用 inbiz()（name (类型) 中文名）', valid),
        ...section('引用不存在于页面组件（重点审查）', dangling),
        ...section('⚠ i18n 缺失 key（平台未返回翻译）', b.brokenI18nKeys),
    ];
    return lines.join('\n');
}
