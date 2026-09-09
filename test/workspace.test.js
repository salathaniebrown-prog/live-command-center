'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../public/index.html'), 'utf8');
test('mission brief preserves executive council with and without authenticated MAX', async () => {
  const source = html.match(/async function missionBrief\(\)\{.*?\}\}/)[0];
  for (const token of ['', 'fixture-token']) {
    const elements = {executive: {textContent: 'council'}, missionOutput: {}, prompt: {}, answer: {textContent: 'verified answer'}};
    let rendered = 0;
    const context = { $: id => elements[id], renderExecutiveCouncil: () => rendered++, localBrief: () => 'local observations', sessionStorage: {getItem: () => token}, askMax: async () => {} };
    vm.createContext(context); vm.runInContext(source, context); await context.missionBrief();
    assert.equal(elements.executive.textContent, 'council');
    assert.equal(elements.missionOutput.textContent, token ? 'verified answer' : 'local observations');
    assert.equal(rendered, 1);
  }
});
