'use strict';
const { spawnSync } = require('node:child_process');
for (const file of ['deployment-center.js', 'public/deployment-center.js', 'scripts/trigger-railway-deployment.js']) {
  const result = spawnSync(process.execPath, ['--check', file], { stdio: 'inherit' });
  if (result.status !== 0) process.exit(1);
}
