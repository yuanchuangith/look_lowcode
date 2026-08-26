// 资源写入：公共编排目录（public-bizflows）+ 四类资源列表（models/dictionaries/datasets/events）。
// 从 writer.ts 拆出（300 行硬指标）；行为与拆分前完全一致（Task 1 纯重构）。
import { join } from 'node:path';
import { displaySlug } from './code-extract.js';
/**
 * 公共编排（Phase 2 改名 public-bizflows）：
 * 代码优先取 design 两步走结果（codes.js/cs）；design 无数据时回退列表 controlCode——
 * 但实测 controlCode 80/81 是空模板 `function action(params){}`，trim 后 ≤30 字符视为空壳不落盘。
 */
export function writePublicBizflows(w, outDir, data) {
    if (data.publicBizflows.length === 0)
        return 0;
    const dir = join(outDir, 'public-bizflows');
    const lines = [
        '# 公共编排清单（全页面共享）', '',
        '| code | 名称 | 启用 | 描述 | 代码 | id |',
        '|------|------|------|------|------|----|',
        ...data.publicBizflows.map(pf => {
            const codes = pf.codes ?? {};
            const fromDesign = [codes.js && 'js', codes.cs && 'cs'].filter(Boolean).join('+');
            let kind = fromDesign;
            if (!kind) {
                if (pf.status === false)
                    kind = '（禁用，未拉取）';
                else
                    kind = controlCodeIsReal(pf.controlCode) ? 'js（列表内联）' : '（平台无代码）';
            }
            // id 列：action.cs 里 InvokeDynamicMethod("<id>",...) 以 id 引用公共编排，需可反查
            return `| ${pf.code} | ${pf.name} | ${pf.status ? '是' : '否'} | ${pf.description ?? '-'} | ${kind} | ${pf.id} |`;
        }),
    ];
    w.write(join(dir, 'README.md'), lines.join('\n') + '\n');
    for (const pf of data.publicBizflows) {
        if (pf.status === false)
            continue; // 禁用：代码目录缺席（含 controlCode 内联回退）
        const flowDir = join(dir, displaySlug(pf.name, pf.code));
        const hasDesignCode = Boolean(pf.codes?.js || pf.codes?.cs);
        if (pf.codes?.js)
            w.write(join(flowDir, 'action.js'), pf.codes.js);
        if (pf.codes?.cs)
            w.write(join(flowDir, 'action.cs'), pf.codes.cs);
        if (!hasDesignCode && controlCodeIsReal(pf.controlCode)) {
            w.write(join(flowDir, 'action.js'), pf.controlCode);
        }
    }
    return data.publicBizflows.length;
}
/** controlCode 是否为真代码（非空模板）：trim 后长度 > 30 判定（模板 27 字符） */
function controlCodeIsReal(controlCode) {
    return Boolean(controlCode && controlCode.trim().length > 30);
}
/** 数据集 config 双重序列化展开：JSON 字符串 → 对象；非法串原样保留（快照不因脏数据中断） */
function expandDatasetConfig(items) {
    return items.map((it) => {
        if (typeof it?.config !== 'string' || !it.config.trim().startsWith('{'))
            return it;
        try {
            return { ...it, config: JSON.parse(it.config) };
        }
        catch {
            return it;
        }
    });
}
/**
 * 资源目录（流程除外——见 writeProcesses 分组层级）：每项一 JSON + README 索引；返回各资源计数。
 * 文件名 = `中文名-code`；无 code 的资源用完整 id（不截断）；同名撞车时追加完整 id。
 */
export function writeResources(w, outDir, data) {
    const writeList = (name, items, slugOf, rowOf) => {
        if (items.length === 0)
            return 0;
        const dir = join(outDir, name);
        const used = new Set();
        const rows = items.map((item, i) => {
            let slug = slugOf(item, i);
            if (used.has(slug))
                slug = `${slug}-${item?.id ?? i}`;
            used.add(slug);
            w.writeJson(join(dir, `${slug}.json`), item);
            return rowOf(item, slug);
        });
        w.write(join(dir, 'README.md'), `# ${name} 索引\n\n| 条目 | 说明 |\n|------|------|\n${rows.join('\n')}\n`);
        return items.length;
    };
    /** 通用资源命名：name/comment + code（缺 code 用完整 id，不截断） */
    const resSlug = (r) => displaySlug(String(r?.name ?? r?.comment ?? ''), String(r?.code || r?.id || ''));
    const counts = {};
    // 模型：name 是英文表名，中文注释在 comment（详情接口字段，列表期可能缺席）
    counts.models = writeList('models', data.models, (m) => displaySlug(String(m.config?.comment || m.name || ''), String(m.config?.code || m.key)), (m, slug) => `| ${slug} | ${m.name} |`);
    counts.dictionaries = writeList('dictionaries', data.dictionaries, resSlug, (d, slug) => `| ${slug} | ${d?.name ?? '-'} |`);
    counts.datasets = writeList('datasets', expandDatasetConfig(data.datasets), resSlug, (d, slug) => `| ${slug} | ${d?.name ?? '-'} |`);
    counts.events = writeList('events', data.events, resSlug, (e, slug) => `| ${slug} | ${e?.name ?? '-'} |`);
    return counts;
}
/** 顶层 README（快照使用说明，AI 的第一入口；从 writer.ts 拆出守 300 行指标） */
export function writeTopReadme(w, outDir, data) {
    w.write(join(outDir, 'README.md'), [
        '# CPM 平台快照',
        '',
        '> **本项目只用于分析问题（只读）**：全部文件由 `cpm pull` 从平台拉取生成。不要直接修改快照里的任何文件（包括 `action.js`/`action.cs` 业务代码）——改动不会同步回平台，且会被下次拉取覆盖。分析出问题后，修改请在平台 web 设计器中操作，完成后 `cpm pull` 刷新快照再验证。',
        '',
        `平台：${data.platform.url}（appId=${data.platform.appId}）。内容最后变化时间与各资源数量见 manifest.json。`,
        '',
        '- 定位页面：读 indexes/pages.md（路由 → 目录的权威映射）',
        '- 理解页面：pages/<页面>/ 下 tree.md（结构）→ components.json（组件清单）→ bindings.md（数据绑定）→ bizflows/（业务代码）',
        '- 影响面：indexes/model-usage.md（主模型 → 页面）',
        '- 公共编排：public-bizflows/（全页面共享，C# 在 action.cs）',
        '- 编排公共方法：public-methods/（action.js 的 relatedAttributes.* 与 action.cs 的 _service.* 平台方法参考源码，读编排代码前先查）',
        '- 审批流程：flows/（按分组组织；README 索引含版本/关联页面，process.xml 是 BPMN 链路，ext.json 是节点审批人/按钮）',
        '- 系统菜单：menus/（功能入口树，README 权威索引）；顶栏应用入口：navigations/',
        '- 接口管理：interfaces/（物理/动态接口定义，requestBody/responseBody 已展开）',
        '- 多语言：languages/（按语种 key→文本映射；菜单/页面名 {multilingual} 占位的翻译查询处）',
        '- 时效：平台配置变更后重新 cpm pull；对比 manifest.pulledAt（内容最后变化时间）与 changes 统计',
        '',
        '## 给 AI 的信息',
        '',
        '- 修改本项目（平台低代码应用）前，先加载 cpm-platform skill（skills/cpm-platform/SKILL.md）：平台背景、快照目录地图、复杂文件结构、cpm CLI 速查；组件细节按需读该 skill 的 references/',
        '- 本快照只读（暂无回写命令，详见顶部说明）：修改配置需在平台 web 设计器操作，完成后 cpm pull 刷新快照再分析',
        '- 真机操作或验证页面行为 → playwright-cli skill',
        '- 读文件顺序：小文件优先（tree.md → components.json → bindings.md），需要组件级细节才读 page.json（1MB+）',
    ].join('\n') + '\n');
}
//# sourceMappingURL=writer-resources.js.map