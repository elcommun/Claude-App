// usage: node capture.js outdir [times...] | --all workers
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const SP = __dirname;
(async () => {
  const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
  const args = process.argv.slice(3);
  let jobs;
  if (args[0] === '--all') { jobs = []; for (let i = 0; i < 1800; i++) jobs.push({ t: i / 30, name: `f${String(i).padStart(4, '0')}.png` }); }
  else jobs = args.map(a => ({ t: +a, name: `t${a}.png` }));
  const workers = args[0] === '--all' ? +(args[1] || 4) : 1;
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--allow-file-access-from-files'] });
  let next = 0, done = 0; const t0 = Date.now();
  await Promise.all(Array.from({ length: workers }, async () => {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    page.on('console', m => { if (m.type() === 'error') console.log('console:', m.text()); });
    page.on('pageerror', e => console.log('pageerror:', e.message));
    await page.goto('file://' + path.join(SP, 'render.html'));
    await page.evaluate(() => window.ready);
    while (next < jobs.length) {
      const j = jobs[next++];
      const url = await page.evaluate(t => window.draw(t), j.t);
      fs.writeFileSync(path.join(out, j.name), Buffer.from(url.split(',')[1], 'base64'));
      if (++done % 100 === 0) console.log(done, ((Date.now() - t0) / 1000).toFixed(1) + 's');
    }
  }));
  await browser.close();
})();
