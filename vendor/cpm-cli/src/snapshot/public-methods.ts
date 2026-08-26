// public-methods 静态资产：BizFlow（业务编排）运行时平台公共方法的参考源码，供 AI 理解快照中
// action.js 的 relatedAttributes.* 与 action.cs 的 _service.* 调用。
// 数据源是平台前后端源码库（gxp2.components / gxp2.web）而非平台端点，随 CLI 版本分发；
// 同步与变化剥离复用 skills-sync 的静态资产机制（writer.ts 统一接线）。
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { syncStaticDir } from './skills-sync.js';
/** 包内资产根：src/snapshot/ 与 dist/snapshot/ 两种运行模式同路径 ../../assets/public-methods（与 SKILL_SRC 同构） */
export const PUBLIC_METHODS_SRC = fileURLToPath(new URL('../../assets/public-methods', import.meta.url));
/** 同步包内 public-methods 资产到 <projectDir>/public-methods/；包内资产缺失返回 null（调用方记 failure） */
export function syncPublicMethods(w, projectDir) {
    return syncStaticDir(w, PUBLIC_METHODS_SRC, join(projectDir, 'public-methods'));
}
