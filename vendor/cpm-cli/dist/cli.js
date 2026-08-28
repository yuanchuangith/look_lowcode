#!/usr/bin/env node
// cpm CLI 入口：命令注册与分发。第一用户是 AI Agent，help 输出保持自解释。
import { readFileSync } from 'node:fs';
import { Command } from 'commander';
import { resolveProjectDir } from './config/store.js';
import { runLogin } from './commands/login.js';
import { runWhoami } from './commands/whoami.js';
import { runPull } from './commands/pull.js';
// 版本号从包内 package.json 读（dist/cli.js 与 src/cli.ts 到包根都是上一级，两种运行模式同路径）
const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const program = new Command();
program.exitOverride();
program
    .name('cpm')
    .description('CPM 低代码平台 AI 配套 CLI：拉取平台配置物化为本地快照')
    .version(pkg.version);
program
    .command('login')
    .description('绑定平台地址，登录并缓存 token（应用/站点用内置默认值）')
    .requiredOption('--url <url>', '平台地址，如 http://cpm.gxp2.com')
    .option('--account <account>', '平台账号（缺省读环境变量 CPM_ACCOUNT）')
    .option('--password <password>', '平台密码（缺省读环境变量 CPM_PASSWORD）')
    .option('--out <dir>', '项目目录（缺省当前目录；绑定与快照的归属地）')
    .action((opts) => runLogin({ ...opts, cwd: process.cwd() }));
program
    .command('whoami')
    .description('显示当前绑定与 token 有效性')
    .option('--out <dir>', '项目目录（缺省当前目录）')
    .action((opts) => runWhoami(resolveProjectDir({ out: opts.out, cwd: process.cwd() }), opts.out ? ` --out ${opts.out}` : ''));
program
    .command('pull')
    .description('拉取平台配置并物化为项目目录快照（平铺于 --out 或当前目录）')
    .option('--page <route|id|outId>', '只拉取单个页面（缺省全量）')
    .option('--out <dir>', '项目目录（缺省当前目录；快照平铺写入）')
    .option('--json', '输出机器可读结果')
    .option('--concurrency <n>', '全局并发上限（缺省 10）')
    .action(async (opts) => {
    await runPull({
        ...opts,
        cwd: process.cwd(),
        concurrency: opts.concurrency ? parseInt(opts.concurrency, 10) : undefined,
    });
});
try {
    await program.parseAsync();
}
catch (error) {
    const code = error?.code;
    if (code === 'commander.helpDisplayed' || code === 'commander.version') {
        process.exitCode = 0;
    }
    else {
        const jsonPull = process.argv.includes('pull') && process.argv.includes('--json');
        if (jsonPull) {
            console.log(JSON.stringify({
                ok: false,
                mode: process.argv.includes('--page') ? 'page' : 'full',
                page: null,
                counts: {},
                changes: { added: 0, updated: 0, removed: 0, removedPaths: [] },
                failures: [],
                health: null,
                durationMs: 0,
                error: { code: 'INVALID_ARGUMENT', message: String(error?.message ?? error) },
            }));
        }
        process.exitCode = Number(error?.exitCode) || 1;
    }
}
//# sourceMappingURL=cli.js.map