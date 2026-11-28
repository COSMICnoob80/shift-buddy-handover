#!/usr/bin/env node
// Drive the real Shift Buddy console in headless Chrome and capture PNG frames.
//
//   node tools/record_console.mjs --mode smoke   --url http://127.0.0.1:8777
//   node tools/record_console.mjs --mode record  --url http://127.0.0.1:8777 --out /tmp/frames
//
// No Xvfb is required: Chrome renders offscreen, CDP captures the real DOM after
// every real state change, and ffmpeg assembles the frames. Every frame is the
// console rendering the run's actual audit-derived data.

import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import os from "node:os";
import path from "node:path";

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : def;
}
const URL_BASE = arg("url", "http://127.0.0.1:8777");
const MODE = arg("mode", "record");
const OUT = arg("out", "/tmp/sbh-frames");
const INTERVAL = Number(arg("interval", "150"));
const CHROME = arg("chrome", process.env.CHROME || "google-chrome");
const DBG = Number(arg("debug-port", String(9300 + Math.floor(Math.random() * 400))));

mkdirSync(OUT, { recursive: true });
const profile = path.join(os.tmpdir(), "sbh-chrome-" + DBG + "-" + Date.now());
mkdirSync(profile, { recursive: true });

const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
  "--mute-audio", "--disable-extensions", "--disable-background-networking",
  "--window-size=1920,1080", "--force-device-scale-factor=1",
  `--user-data-dir=${profile}`, `--remote-debugging-port=${DBG}`,
  "about:blank",
], { stdio: ["ignore", "ignore", "ignore"] });

const BASE = `http://127.0.0.1:${DBG}`;

async function waitJson(pathname, tries = 100) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(BASE + pathname);
      if (r.ok) return await r.json();
    } catch (_) {}
    await sleep(100);
  }
  throw new Error("chrome debug endpoint not ready: " + pathname);
}

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      }
    };
  }
  send(method, params = {}) {
    return new Promise((res, rej) => {
      const id = ++this.id;
      this.pending.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
}

async function main() {
  // Wait for chrome, find the page target.
  await waitJson("/json/version");
  const targets = await waitJson("/json/list");
  const page = targets.find((t) => t.type === "page");
  if (!page) throw new Error("no page target");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  const cdp = new CDP(ws);

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false,
  });
  await cdp.send("Page.navigate", { url: URL_BASE + "/" });
  for (let i = 0; i < 80; i++) {
    const rs = await evalJS(cdp, "document.readyState");
    if (rs === "complete") break;
    await sleep(100);
  }
  await sleep(600);

  const errors = [];
  cdp.ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === "Runtime.exceptionThrown") {
      errors.push(m.params.exceptionDetails?.exception?.description || "exception");
    }
  });

  const click = (sel) => evalJS(cdp, `(()=>{const e=document.querySelector(${JSON.stringify(sel)}); if(!e) return 'missing'; e.click(); return 'ok';})()`);
  const text = (sel) => evalJS(cdp, `(document.querySelector(${JSON.stringify(sel)})||{}).textContent||''`);
  const chip = () => text("#runChip");

  let frames = 0;
  let capturing = true;
  const startedAt = Date.now();
  async function shot() {
    const r = await cdp.send("Page.captureScreenshot", { format: "jpeg", quality: 85 });
    writeFileSync(path.join(OUT, "frame_" + String(frames).padStart(6, "0") + ".jpg"),
      Buffer.from(r.data, "base64"));
    frames++;
  }
  async function captureLoop() {
    while (capturing) {
      try { await shot(); } catch (_) {}
      await sleep(INTERVAL);
    }
  }

  async function waitFor(fn, timeoutMs, label) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      if (await fn()) return true;
      await sleep(120);
    }
    console.log("timeout waiting for", label);
    return false;
  }

  if (MODE === "smoke") {
    await click("#startRun");
    await waitFor(async () => (await chip()).includes("complete"), 60000, "complete");
    await sleep(500);
    const state = await evalJS(cdp, `JSON.stringify({
      chip: (document.getElementById('runChip')||{}).textContent,
      pages: (document.getElementById('cPages')||{}).textContent,
      patients: (document.getElementById('cPatients')||{}).textContent,
      refused: (document.getElementById('cRefused')||{}).textContent,
      facts: (document.getElementById('cFacts')||{}).textContent,
      invented: (document.getElementById('cInvented')||{}).textContent
    })`);
    await click('[data-screen="3"]');
    await sleep(400);
    const sbar = await evalJS(cdp, `(document.getElementById('docHost')||{}).innerText||''`);
    const sbarKind = await evalJS(cdp, `document.querySelector('#docHost .doc')?'sbar-'+document.querySelector('#docHost .doc').outerHTML.includes('<!--sbar-->'):''`);
    await click('[data-mode="ward"]');
    await sleep(300);
    const ward = await evalJS(cdp, `(document.getElementById('docHost')||{}).innerText||''`);
    await click('[data-screen="5"]');
    await sleep(300);
    const audit = await evalJS(cdp, `JSON.stringify({count:(document.getElementById('auditCount')||{}).textContent, chain:(document.getElementById('chainState')||{}).textContent.trim()})`);
    console.log("SMOKE state:", state);
    console.log("SMOKE audit:", audit);
    console.log("SMOKE sbar len", sbar.length, "ward len", ward.length, "same facts?", sbar.replace(/\\s+/g,' ').includes('BED') || sbar.length>0);
    console.log("SMOKE sbar head:", sbar.slice(0, 160).replace(/\\n/g, " | "));
    console.log("SMOKE ward head:", ward.slice(0, 160).replace(/\\n/g, " | "));
    console.log("SMOKE errors:", errors.length ? errors : "none");
    await shot();
    capturing = false;
    ws.close(); chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch (_) {}
    return;
  }

  // ------------------------------------------------ record timeline
  console.log("warming scorecard cache (real harness)…");
  try {
    await fetch(URL_BASE + "/api/scorecard", { method: "POST" });
  } catch (_) {}

  const capPromise = captureLoop();
  await sleep(1800);                      // trigger screen
  await click("#startRun");
  await waitFor(async () => (await chip()).includes("running"), 8000, "running");
  await sleep(3800);                      // live: watch pages stream in
  await click("#killRail");               // real STOP mid-run
  await waitFor(async () => (await chip()).includes("halted"), 8000, "halted");
  await sleep(2600);                      // halt banner + audit stop record
  await click("#haltRestart");            // fresh run
  await waitFor(async () => (await chip()).includes("running"), 8000, "rerun running");
  await waitFor(async () => (await chip()).includes("complete"), 60000, "full complete");
  await sleep(600);
  await click('[data-screen="3"]');       // handoff, SBAR
  await sleep(3200);
  await click('[data-mode="ward"]');      // same facts, ward layout
  await sleep(3200);
  await click('[data-screen="5"]');       // audit + kill (real records)
  await sleep(2600);
  await click("#runScorecard");           // cached real 40/40
  await sleep(2600);
  await click('[data-screen="4"]');       // assisted (honest, not wired)
  await sleep(2200);

  capturing = false;
  await capPromise;
  const elapsed = (Date.now() - startedAt) / 1000;
  writeFileSync(path.join(OUT, "meta.json"),
    JSON.stringify({ frames, elapsed, fps: frames / elapsed, errors }, null, 2));
  console.log(`frames=${frames} elapsed=${elapsed.toFixed(1)}s fps=${(frames / elapsed).toFixed(2)} errors=${errors.length}`);
  ws.close(); chrome.kill("SIGKILL");
  try { rmSync(profile, { recursive: true, force: true }); } catch (_) {}
}

async function evalJS(cdp, expression) {
  const r = await cdp.send("Runtime.evaluate", {
    expression, returnByValue: true, awaitPromise: true,
  });
  return r.result ? r.result.value : undefined;
}

main().catch((e) => { console.error("FATAL", e); try { chrome.kill("SIGKILL"); } catch (_) {} process.exit(1); });
