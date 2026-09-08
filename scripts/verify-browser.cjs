'use strict';
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const [name, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
      await page.setViewportSize({ width, height });
      await page.goto(process.env.EAGLE_EYES_TEST_URL || 'http://127.0.0.1:31338', { waitUntil: 'domcontentloaded' });
      assert.match(await page.title(), /CHRONICLE LAB V13/);
      for (const section of ['world', 'live', 'lab', 'intel', 'links', 'max']) {
        await page.locator(`nav a[href="#${section}"]`).click();
        assert.equal(await page.evaluate(() => location.hash), `#${section}`);
        assert.equal(await page.locator(`#${section}`).count(), 1);
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${name} horizontal overflow`);
      await page.screenshot({ path: `/tmp/eagle-eyes-${name}.png`, fullPage: true });
    }
    assert.deepEqual(errors, []);
    console.log('V13 desktop/mobile navigation and JavaScript checks passed');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
