/** 页面总览：权威映射表（route → 目录）+ 每页一行概述。AI 定位页面的第一入口。 */
export function renderPagesIndex(entries) {
    const lines = [
        '# 页面总览（权威映射表）',
        '',
        '| 路由 | 名称 | 目录 | 概述 |',
        '|------|------|------|------|',
        ...entries.map(e => `| ${e.route} | ${e.name} | ${e.dir} | ${e.summary} |`),
        '',
        '页面目录内：page.json（原始 Schema）/ tree.md（组件树）/ bindings.md（绑定清单）/ bizflows/（业务规则代码）。',
    ];
    // 重复路由冲突检测
    const byRoute = new Map();
    for (const e of entries) {
        if (!byRoute.has(e.route))
            byRoute.set(e.route, []);
        byRoute.get(e.route).push(e.dir);
    }
    const conflicts = [...byRoute.entries()].filter(([, dirs]) => dirs.length > 1);
    if (conflicts.length > 0) {
        lines.push('', '## ⚠ 路由冲突', '生效版本需真机确认', '');
        for (const [route, dirs] of conflicts) {
            lines.push(`- ${route}：${dirs.join('、')}`);
        }
    }
    return lines.join('\n');
}
/**
 * 模型 → 使用它的页面目录列表（影响面分析入口）。
 * models 传入时：表头加名称列（comment 中文注释优先、name 次之），并追加
 * 「未被页面主模型引用」段（可能是子表/关联模型、数据集专用模型或已废弃）。
 */
export function renderModelUsage(pages, models = []) {
    const usage = new Map();
    for (const p of pages) {
        const m = p.bindings.mainModel; // Phase 2：仅统计 form.model 主模型
        if (!m)
            continue;
        if (!usage.has(m.modelKey))
            usage.set(m.modelKey, []);
        usage.get(m.modelKey).push(p.dir);
    }
    const label = (m) => String(m.comment || m.name || '-');
    const byKey = new Map(models.map(m => [m.key, m]));
    const usedRows = [...usage.entries()].map(([k, dirs]) => {
        const m = byKey.get(k);
        return `| ${k} | ${m ? label(m) : '-'} | ${dirs.join('、')} |`;
    });
    const lines = [
        '# 模型使用索引（影响面入口）',
        '',
        '| 模型 | 名称 | 使用页面 |',
        '|------|------|----------|',
        ...usedRows, '',
        '改模型前先查此表：列出的是绑定该模型的页面，需逐一核对字段兼容性。',
    ];
    if (models.length > 0) {
        const unused = models.filter(m => !usage.has(m.key))
            .map(m => `| ${m.key} | ${label(m)} | - |`);
        lines.push('', '## 未被页面主模型引用', '', '（可能是子表/关联模型、数据集专用模型或已废弃；改这些模型的影响面需查数据集与代码引用）', '', '| 模型 | 名称 | 使用页面 |', '|------|------|----------|', ...unused, '');
    }
    return lines.join('\n');
}
/** 组件类型 → 使用它的页面目录列表 */
export function renderComponentUsage(pages) {
    const usage = new Map();
    for (const p of pages) {
        for (const t of p.componentTypes) {
            if (!usage.has(t))
                usage.set(t, []);
            usage.get(t).push(p.dir);
        }
    }
    const lines = [
        '# 组件使用索引',
        '',
        '| 组件类型 | 使用页面 |',
        '|----------|----------|',
        ...[...usage.entries()].map(([t, dirs]) => `| ${t} | ${dirs.join('、')} |`),
    ];
    return lines.join('\n');
}
/** 事件 → 订阅页面/规则 反向索引（排查"这个事件触发了什么"的入口） */
export function renderEventUsage(subs) {
    const byEvent = new Map();
    for (const s of subs) {
        if (!byEvent.has(s.eventCode))
            byEvent.set(s.eventCode, { eventName: s.eventName, rows: [] });
        byEvent.get(s.eventCode).rows.push(`\`${s.ruleCode}\` ${s.ruleName} → ${s.pageDir}`);
    }
    return [
        '# 事件订阅索引（事件 → 订阅方）', '',
        '| 事件 code | 事件名称 | 订阅（规则 → 页面） |', '|------|------|------|',
        ...[...byEvent.entries()].map(([code, v]) => `| ${code} | ${v.eventName} | ${v.rows.join('；')} |`), '',
        '数据来源：页面规则 action.js 中 relatedAttributes.eventson(事件Key, 回调) 的静态提取',
        '（2026-08-26 本地考古；平台 BizFlow 列表的 event 字段实测为空串，设计响应亦无映射）。',
        '事件注册表读 events/（code/eventCode/name）；页面级规则明细读 pages/<页面>/bizflows/README.md。',
    ].join('\n');
}
