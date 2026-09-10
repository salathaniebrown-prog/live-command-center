'use strict';

const { spawnSync } = require('node:child_process');

const isRender = String(process.env.RENDER || '').toLowerCase() === 'true';
const command = isRender ? process.execPath : (process.platform === 'win32' ? 'npm.cmd' : 'npm');
const args = isRender ? ['scripts/verify-global-static.js'] : ['run', 'ci'];

console.log(`[build] target=${isRender ? 'render-static' : 'standard-ci'}`);

const result = spawnSync(command, args, {
  stdio: 'inherit',
  env: process.env,
});

if (result.error) {
  console.error('[build] failed to start build command:', result.error.message);
  process.exit(1);
}

process.exit(Number.isInteger(result.status) ? result.status : 1);
