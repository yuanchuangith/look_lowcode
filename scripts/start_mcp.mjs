import { existsSync } from 'node:fs';
import { homedir, platform } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

function runtimeRoot() {
  if (process.env.GXP_LOWCODE_RUNTIME_ROOT) return resolve(process.env.GXP_LOWCODE_RUNTIME_ROOT);
  if (platform() === 'win32') {
    return join(process.env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local'), 'GxpLowcodeReadonly');
  }
  if (platform() === 'darwin') {
    return join(homedir(), 'Library', 'Application Support', 'GxpLowcodeReadonly');
  }
  return join(process.env.XDG_DATA_HOME || join(homedir(), '.local', 'share'), 'GxpLowcodeReadonly');
}

const scriptDir = dirname(fileURLToPath(import.meta.url));
const pluginRoot = resolve(scriptDir, '..');
const root = runtimeRoot();
const python = platform() === 'win32'
  ? join(root, '.venv', 'Scripts', 'python.exe')
  : join(root, '.venv', 'bin', 'python');

if (!existsSync(python)) {
  process.stderr.write(`Look runtime is missing. Run ${join(pluginRoot, 'scripts', 'setup.py')} first.\n`);
  process.exit(1);
}

const child = spawnSync(python, [join(pluginRoot, 'mcp', 'server.py')], {
  cwd: pluginRoot,
  env: process.env,
  stdio: 'inherit',
  windowsHide: true,
});
if (child.error) throw child.error;
process.exit(child.status ?? 1);
