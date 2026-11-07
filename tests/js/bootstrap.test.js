// Regression tests for the TypeType WebView bootstrap embedded in ci/patches/YouTubeView.swift.
// Runs the real script in a vm against a fake DOM / Web Audio. Usage: node tests/js/bootstrap.test.js
const fs = require("fs"), vm = require("vm"), path = require("path"), assert = require("assert");
const swift = fs.readFileSync(path.join(__dirname, "../../ci/patches/YouTubeView.swift"), "utf8");
const source = swift.split('static let bootstrap = #"""')[1].split('"""#')[0];

function makeEnv({ ctx = "running", crossOrigin = false, throwCtx = false, signal = true, captureThrows = false } = {}) {
  const posts = []; let now = 0, timers = [], nextId = 1;
  const listeners = new Map();
  const makeVideo = (src) => {
    const handlers = {};
    const v = { currentSrc: src, src, paused: true, ended: false, muted: false, volume: 1, readyState: 4, currentTime: 0, duration: 100, isConnected: true,
      crossOrigin: null, error: null, seekable: { length: 0 },
      addEventListener(n, h) { (handlers[n] ||= new Set()).add(h); }, removeEventListener(n, h) { handlers[n]?.delete(h); },
      emit(n) { (handlers[n] || []).forEach(h => h()); }, count(n) { return (handlers[n] || new Set()).size; },
      closest: () => ({}), play() { v.paused = false; v.emit("play"); v.emit("playing"); return Promise.resolve(); }, pause() { v.paused = true; v.emit("pause"); } };
    return v;
  };
  const state = { videos: [], menus: {}, contexts: [], captures: [] };
  class Ctx {
    constructor() { if (throwCtx) throw new Error("no webaudio"); this.state = ctx; this.closed = false; state.contexts.push(this); this.destination = {}; }
    resume() { return ctx === "suspended" ? new Promise(() => {}) : Promise.resolve(); }
    close() { this.closed = true; return Promise.resolve(); }
    addEventListener() {}
    createMediaElementSource(el) { if (captureThrows) throw new Error("InvalidStateError"); state.captures.push(el); return node(); }
    createBiquadFilter() { return { ...node(), gain: { value: 0 }, frequency: { value: 0 }, Q: { value: 0 } }; }
    createGain() { return { ...node(), gain: { value: 1 } }; }
    createAnalyser() { return { ...node(), fftSize: 1024, getFloatTimeDomainData: a => { a[0] = signal ? 0.2 : 0; } }; }
  }
  const node = () => ({ connect() {}, disconnect() {} });
  const sandbox = {
    console, URL, Float32Array, Promise, Math, Number, String, Array, Object, WeakSet, Set,
    Date: { now: () => now },
    location: { href: "https://watch.typetype.video/watch?v=x", origin: "https://watch.typetype.video" },
    document: { querySelectorAll: sel => sel === "video" ? state.videos.filter(v => v.isConnected) : [], querySelector: sel => state.menus[sel] || null, getElementById: () => null },
    MutationObserver: class { observe() {} }, AudioContext: Ctx,
    setTimeout: (fn, ms = 0) => { const id = nextId++; timers.push({ id, at: now + ms, fn }); return id; },
    clearTimeout: id => { timers = timers.filter(t => t.id !== id); },
    setInterval: (fn, ms) => { const id = nextId++; timers.push({ id, at: now + ms, fn, every: ms }); return id; },
    clearInterval: id => { timers = timers.filter(t => t.id !== id); },
    addEventListener: (n, h) => listeners.set(n, h),
  };
  sandbox.window = sandbox;
  sandbox.window.webkit = { messageHandlers: { trapPlayer: { postMessage: m => posts.push(m) } } };
  if (throwCtx) sandbox.AudioContext = function () { throw new Error("no webaudio"); };
  vm.createContext(sandbox);
  const advance = async ms => { const end = now + ms; while (now < end) { now += 50; for (const t of timers.filter(t => t.at <= now)) { if (t.every) t.at += t.every; else timers = timers.filter(x => x.id !== t.id); try { t.fn(); } catch (e) {} } for (let i = 0; i < 20; i++) await Promise.resolve(); } };
  return { posts, state, sandbox, makeVideo, advance, run: () => vm.runInContext(source, sandbox) };
}
const eqStates = e => e.posts.filter(p => p.type === "eqStatus").map(p => p.state);
const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test("playback state and native controls work even when Web Audio throws", async () => {
  const e = makeEnv({ throwCtx: true }); const v = e.makeVideo("blob:https://watch.typetype.video/1"); e.state.videos.push(v); e.run();
  await e.advance(100); v.paused = false; v.emit("play"); await e.advance(100);
  assert(e.posts.some(p => p.type === "state" && p.paused === false), "state posted");
  assert(eqStates(e).includes("unavailable"), "EQ unavailable reported");
  assert(!e.posts.some(p => p.type === "playerError"), "no playback error attributed to EQ");
  e.sandbox.__traptubeControl("pause"); assert.strictEqual(v.paused, true);
  e.sandbox.__traptubeControl("play"); assert.strictEqual(v.paused, false);
});
test("cross-origin media without CORS is never captured (no silent playback)", async () => {
  const e = makeEnv(); const v = e.makeVideo("https://rr1.googlevideo.com/videoplayback?x"); v.paused = false; e.state.videos.push(v); e.run();
  await e.advance(200);
  assert.strictEqual(e.state.captures.length, 0, "createMediaElementSource must not be called");
  const last = e.posts.filter(p => p.type === "eqStatus").pop(); assert.strictEqual(last.state, "unavailable"); assert(/CORS/.test(last.message));
});
test("EQ is reported active only after signal is measured through the graph", async () => {
  const e = makeEnv(); const v = e.makeVideo("blob:https://watch.typetype.video/2"); v.paused = false; e.state.videos.push(v); e.run();
  await e.advance(100); assert.strictEqual(e.state.captures.length, 1);
  assert(!eqStates(e).includes("active") || e.posts.findIndex(p => p.state === "active") > -1);
  await e.advance(1000); assert(eqStates(e).includes("active"));
});
test("a suspended audio context never captures the element and ends as unavailable", async () => {
  const e = makeEnv({ ctx: "suspended" }); const v = e.makeVideo("blob:https://watch.typetype.video/3"); v.paused = false; e.state.videos.push(v); e.run();
  await e.advance(12000);
  assert.strictEqual(e.state.captures.length, 0);
  assert.strictEqual(eqStates(e).pop(), "unavailable");
});
test("silent output through the graph becomes unavailable with a reload option, not 'active'", async () => {
  const e = makeEnv({ signal: false }); const v = e.makeVideo("blob:https://watch.typetype.video/4"); v.paused = false; e.state.videos.push(v); e.run();
  await e.advance(6000);
  assert(!eqStates(e).includes("active"));
  const last = e.posts.filter(p => p.type === "eqStatus").pop(); assert.strictEqual(last.state, "unavailable"); assert.strictEqual(last.canReload, true);
});
test("replacing the video element tears down listeners, filters and context; same element is never captured twice", async () => {
  const e = makeEnv(); const a = e.makeVideo("blob:https://watch.typetype.video/a"); a.paused = false; e.state.videos.push(a); e.run(); await e.advance(300);
  assert.strictEqual(e.state.contexts.length, 1); const before = a.count("timeupdate"); assert(before >= 1);
  a.isConnected = false; const b = e.makeVideo("blob:https://watch.typetype.video/b"); b.paused = false; e.state.videos = [a, b];
  await e.advance(1500);
  assert.strictEqual(a.count("timeupdate"), 0, "old listeners removed"); assert(e.state.contexts[0].closed, "old context closed");
  assert.strictEqual(e.state.contexts.length, 2); assert.strictEqual(e.state.captures.filter(x => x === a).length, 1);
  assert(b.count("timeupdate") >= 1, "new element bound");
});
test("failure after capture reconnects audio directly instead of leaving silence", async () => {
  const e = makeEnv({ captureThrows: true }); const v = e.makeVideo("blob:https://watch.typetype.video/5"); v.paused = false; e.state.videos.push(v); e.run();
  await e.advance(300); assert.strictEqual(eqStates(e).pop(), "unavailable");
});
test("media element errors are playback errors, not EQ status", async () => {
  const e = makeEnv(); const v = e.makeVideo("blob:https://watch.typetype.video/6"); e.state.videos.push(v); e.run(); await e.advance(100);
  v.error = { code: 4, message: "" }; v.emit("error");
  assert(e.posts.some(p => p.type === "playerError" && /not supported/.test(p.message)));
});
test("menu options use stable ids and selection rejects a stale or mismatched option", async () => {
  const e = makeEnv(); const v = e.makeVideo("blob:https://watch.typetype.video/7"); e.state.videos.push(v);
  const opt = (value, label, on) => ({ _a: { value }, getAttribute(n) { return n === "aria-checked" ? String(!!on) : (n === "data-value" ? value : null); }, hasAttribute: () => false, innerText: label, clicked: 0, click() { this.clicked++; } });
  const items = [opt("137", "1080p"), opt("136", "720p", true), opt("135", "720p")];
  const trigger = { getAttribute: () => "false", click() {} };
  e.state.menus[".typetype-quality-menu"] = { querySelector: s => (s === ".vds-menu-items" ? { querySelectorAll: () => items } : trigger) };
  e.run(); await e.advance(2000);
  const listing = e.posts.filter(p => p.type === "videoQualities").pop().items;
  assert.deepStrictEqual(listing.map(i => i.id), ["v:137", "v:136", "v:135"]);
  e.sandbox.__traptubeSelectOption({ kind: "video", id: "v:135", label: "720p" }); await e.advance(800);
  assert.strictEqual(items[2].clicked, 1); assert.strictEqual(items[1].clicked, 0, "duplicate label must not hit the wrong item");
  e.sandbox.__traptubeSelectOption({ kind: "video", id: "v:999", label: "4K" }); await e.advance(800);
  assert(e.posts.some(p => p.type === "menuNotice"));
});

(async () => {
  let failed = 0;
  for (const [name, fn] of tests) { try { await fn(); console.log("PASS", name); } catch (err) { failed++; console.log("FAIL", name, "\n   ", err && err.message); } }
  console.log(failed ? `${failed} FAILED` : "ALL PASSED"); process.exit(failed ? 1 : 0);
})();
