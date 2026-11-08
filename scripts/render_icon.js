// Renders abydex.svg to PNGs (node scripts/render_icon.js). Needs Playwright + Chromium.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const dir = path.join(__dirname, '..', 'abydex', 'webui', 'static');
  const svg = fs.readFileSync(path.join(dir, 'abydex.svg'), 'utf8');
  const out = process.argv[2] || dir;
  const b = await chromium.launch();
  for (const s of [16, 24, 32, 48, 64, 128, 256, 512]) {
    const p = await b.newPage({ viewport: { width: s, height: s } });
    await p.setContent(`<html><body style="margin:0;background:transparent">${svg.replace('width="512" height="512"', `width="${s}" height="${s}"`)}</body></html>`);
    await p.screenshot({ path: path.join(out, `icon-${s}.png`), omitBackground: true });
    await p.close();
  }
  await b.close();
})();
