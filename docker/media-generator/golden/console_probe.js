// Loads one composition in headless Chrome and reports console errors, uncaught page errors, failed
// requests, and whether window.__hf.buildReady.shaders is set. Prints one JSON line on stdout.
// Run inside the media-generator image:  NODE_PATH=<hyperframes>/node_modules node console_probe.js <index.html>
'use strict';
const puppeteer = require('puppeteer-core');

const CHROME = process.env.CHROME_PATH || '/usr/local/bin/chrome-headless-shell';
const SEEK_TIMES = [0.5, 1];

function emit(result) {
  console.log(JSON.stringify(result));
}

(async () => {
  const file = process.argv[2];
  const errors = [];
  const warnings = [];
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: [
      '--no-sandbox',
      '--use-angle=swiftshader',
      '--use-vulkan=swiftshader',
      '--enable-unsafe-swiftshader',
      '--enable-unsafe-webgpu',
      '--ignore-gpu-blocklist',
    ],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push({ type: 'console.error', text: m.text() });
      else if (m.type() === 'warning') warnings.push(m.text());
    });
    page.on('pageerror', (e) => errors.push({ type: 'pageerror', text: String(e && e.message ? e.message : e) }));
    page.on('requestfailed', (r) => errors.push({ type: 'requestfailed', text: r.url() }));
    await page.goto('file://' + file, { waitUntil: 'load', timeout: 60000 });

    const isReady = () => page.evaluate(() => !!(window.__hf && window.__hf.buildReady && window.__hf.buildReady.shaders));
    let ready = false;
    for (let i = 0; i < 300 && !ready; i++) {
      ready = await isReady();
      if (!ready) await new Promise((r) => setTimeout(r, 100));
    }
    for (const t of SEEK_TIMES) {
      await page.evaluate((time) => {
        window.dispatchEvent(new CustomEvent('hf-seek', { detail: { time } }));
      }, t);
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    }
    emit({ buildReadyShaders: ready, errors, warnings: warnings.length });
  } finally {
    await browser.close();
  }
})().catch((e) => {
  emit({ buildReadyShaders: false, errors: [{ type: 'probe', text: String(e && e.message ? e.message : e) }], warnings: 0 });
});
