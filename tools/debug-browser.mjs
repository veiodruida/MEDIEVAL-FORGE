#!/usr/bin/env node
// Browser debug harness — captures console + page errors + failed network requests
// for a Medieval Forge dev session, dumps to .planning/debug/browser-log-<ts>.txt.
//
// Usage:
//   node tools/debug-browser.mjs                              # default URL, 8s capture
//   node tools/debug-browser.mjs --url http://localhost:5173/projects/abc  # specific page
//   node tools/debug-browser.mjs --duration 15                # capture for 15s
//   node tools/debug-browser.mjs --actions actions.json       # run scripted clicks/evals
//   node tools/debug-browser.mjs --headed                     # show browser window
//
// actions.json format (array of steps, executed sequentially):
//   [
//     { "type": "wait", "ms": 2000 },
//     { "type": "click", "selector": "button:has-text('Editar')" },
//     { "type": "eval", "code": "document.querySelectorAll('.konvajs-content').length" },
//     { "type": "screenshot", "name": "after-edit-click" }
//   ]
//
// Output: log file path printed on the LAST stdout line. Read via Claude's Read tool.

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');
const LOG_DIR = resolve(REPO_ROOT, '.planning/debug');
mkdirSync(LOG_DIR, { recursive: true });

function arg(name, defVal = null) {
  const i = process.argv.indexOf(name);
  if (i === -1) return defVal;
  return process.argv[i + 1] ?? true;
}

const URL = arg('--url', 'http://localhost:5173/');
const DURATION_MS = parseInt(arg('--duration', '8'), 10) * 1000;
const ACTIONS_FILE = arg('--actions', null);
const HEADED = process.argv.includes('--headed');

const ts = new Date().toISOString().replace(/[:.]/g, '-');
const LOG_FILE = resolve(LOG_DIR, `browser-log-${ts}.txt`);
const SCREENSHOT_DIR = resolve(LOG_DIR, 'screenshots');
mkdirSync(SCREENSHOT_DIR, { recursive: true });

const events = [];
function pushEvent(category, payload) {
  events.push({ t: Date.now(), category, ...payload });
}

const browser = await chromium.launch({ headless: !HEADED });
const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const page = await context.newPage();

page.on('console', (msg) => {
  pushEvent('console', {
    type: msg.type(),
    text: msg.text(),
    location: msg.location(),
  });
});

page.on('pageerror', (err) => {
  pushEvent('pageerror', {
    name: err.name,
    message: err.message,
    stack: err.stack,
  });
});

page.on('requestfailed', (req) => {
  pushEvent('requestfailed', {
    url: req.url(),
    method: req.method(),
    failure: req.failure()?.errorText,
  });
});

page.on('response', (resp) => {
  const status = resp.status();
  if (status >= 400) {
    pushEvent('http_error', {
      url: resp.url(),
      status,
      statusText: resp.statusText(),
    });
  }
});

let actions = [];
if (ACTIONS_FILE) {
  try {
    actions = JSON.parse(readFileSync(resolve(REPO_ROOT, ACTIONS_FILE), 'utf8'));
  } catch (e) {
    pushEvent('harness', { msg: `actions file load failed: ${e.message}` });
  }
}

let navigationOk = false;
try {
  pushEvent('harness', { msg: `navigating to ${URL}` });
  const resp = await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
  pushEvent('harness', { msg: `navigation status: ${resp?.status()}` });
  navigationOk = resp && resp.ok();
} catch (e) {
  pushEvent('harness', { msg: `navigation failed: ${e.message}` });
}

if (navigationOk) {
  // baseline settle
  await page.waitForTimeout(2000);

  for (const action of actions) {
    try {
      if (action.type === 'wait') {
        pushEvent('action', { type: 'wait', ms: action.ms });
        await page.waitForTimeout(action.ms);
      } else if (action.type === 'click') {
        pushEvent('action', { type: 'click', selector: action.selector });
        await page.click(action.selector, { timeout: 5000 });
      } else if (action.type === 'fill') {
        pushEvent('action', { type: 'fill', selector: action.selector, value: action.value });
        await page.fill(action.selector, action.value, { timeout: 5000 });
      } else if (action.type === 'eval') {
        const result = await page.evaluate(action.code);
        pushEvent('action', { type: 'eval', code: action.code, result });
      } else if (action.type === 'screenshot') {
        const name = action.name || `step-${Date.now()}`;
        const path = resolve(SCREENSHOT_DIR, `${name}.png`);
        await page.screenshot({ path, fullPage: true });
        pushEvent('action', { type: 'screenshot', path });
      } else if (action.type === 'press') {
        pushEvent('action', { type: 'press', key: action.key });
        await page.keyboard.press(action.key);
      } else {
        pushEvent('harness', { msg: `unknown action: ${action.type}` });
      }
    } catch (e) {
      pushEvent('action_error', { type: action.type, error: e.message });
    }
  }

  // tail capture window after actions complete
  const remaining = Math.max(0, DURATION_MS - actions.reduce((s, a) => s + (a.ms || 200), 2000));
  if (remaining > 0) await page.waitForTimeout(remaining);
}

// always capture a final screenshot
try {
  const finalPath = resolve(SCREENSHOT_DIR, `final-${ts}.png`);
  await page.screenshot({ path: finalPath, fullPage: true });
  pushEvent('harness', { msg: `final screenshot: ${finalPath}` });
} catch {}

await browser.close();

// pretty log
const lines = [];
lines.push(`# Browser Debug Session — ${ts}`);
lines.push(`# URL: ${URL}`);
lines.push(`# Duration: ${DURATION_MS}ms`);
lines.push(`# Actions run: ${actions.length}`);
lines.push(`# Events captured: ${events.length}`);
lines.push('');

const counts = {};
for (const e of events) counts[e.category] = (counts[e.category] || 0) + 1;
lines.push(`## Summary`);
for (const [cat, n] of Object.entries(counts)) lines.push(`  ${cat}: ${n}`);
lines.push('');

lines.push('## Events (chronological)');
const t0 = events[0]?.t ?? Date.now();
for (const e of events) {
  const dt = `+${(e.t - t0)}ms`;
  const { t, category, ...rest } = e;
  lines.push(`[${dt}] [${category}] ${JSON.stringify(rest)}`);
}

writeFileSync(LOG_FILE, lines.join('\n'));
console.log(LOG_FILE);
