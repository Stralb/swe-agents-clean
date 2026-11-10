#!/usr/bin/env python3
# Frozen, task-specific probes only; no security warning text or generated-code locations.
TESTS = {
 668: r'''import { test, expect } from "vitest";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { DEFAULT_HUD_CONFIG } from "../hud/types.js";
import { readHudConfig, writeHudConfig } from "../hud/state.js";
import { render } from "../hud/render.js";

test("task 668: new Git elements are opt-in and disabled by default", () => {
  expect(DEFAULT_HUD_CONFIG.elements.gitRepo).toBe(false);
  expect(DEFAULT_HUD_CONFIG.elements.gitBranch).toBe(false);
});

test("task 668: settings.json omcHud overrides legacy HUD config, with fallback fields", () => {
  const home = process.env.HOME!;
  mkdirSync(join(home, ".claude", ".omc"), { recursive: true });
  writeFileSync(join(home, ".claude", ".omc", "hud-config.json"), JSON.stringify({
    preset: "focused", elements: { cwd: true, gitRepo: false, gitBranch: false }, thresholds: { contextWarning: 12 }
  }));
  writeFileSync(join(home, ".claude", "settings.json"), JSON.stringify({
    unrelatedSetting: "preserve-me", omcHud: { elements: { cwd: false, gitRepo: true, gitBranch: true } }
  }));
  const config: any = readHudConfig();
  expect(config.elements.gitRepo).toBe(true);
  expect(config.elements.gitBranch).toBe(true);
  expect(config.elements.cwd).toBe(false);
  expect(writeHudConfig(config)).toBe(true);
  const updated = JSON.parse(readFileSync(join(home, ".claude", "settings.json"), "utf8"));
  expect(updated.unrelatedSetting).toBe("preserve-me");
  expect(updated.omcHud.elements.gitRepo).toBe(true);
});

test("task 668: display Git repo name and branch in a separate first line", async () => {
  const repo = mkdtempSync(join(tmpdir(), "issue668-git-"));
  try {
    execFileSync("git", ["init", "-q", "-b", "feature/acceptance", repo]);
    execFileSync("git", ["-C", repo, "remote", "add", "origin", "git@github.com:example/issue668-alpha.git"]);
    const elements = { ...DEFAULT_HUD_CONFIG.elements, gitRepo: true, gitBranch: true,
      maxOutputLines: 6, cwd: false, rateLimits: false, agents: false, omcLabel: true };
    const config: any = { ...DEFAULT_HUD_CONFIG, preset: "focused", elements };
    const ctx: any = { cwd: repo, activeAgents: [], todos: [], backgroundTasks: [] };
    const rendered = await render(ctx, config);
    const lines = rendered.split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(2);
    expect(lines[0]).toContain("issue668-alpha");
    expect(lines[0]).toContain("feature/acceptance");
    expect(lines[1]).toContain("OMC");
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});
test("task 668: cwd, repository and branch belong together on line one", async () => {
  const repo=mkdtempSync(join(tmpdir(),"issue668-workdir-"));
  try {
    execFileSync("git",["init","-q","-b","feature/line-one",repo]);
    execFileSync("git",["-C",repo,"remote","add","origin","https://github.com/example/remote-project.git"]);
    const elements={...DEFAULT_HUD_CONFIG.elements,cwd:true,cwdFormat:"relative",gitRepo:true,
      gitBranch:true,rateLimits:false,agents:false,maxOutputLines:6,omcLabel:true};
    const config:any={...DEFAULT_HUD_CONFIG,preset:"focused",elements};
    const ctx:any={cwd:repo,activeAgents:[],todos:[],backgroundTasks:[]};
    const lines=(await render(ctx,config)).split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(2);
    expect(lines[0]).toContain("remote-project");
    expect(lines[0]).toContain("feature/line-one");
    expect(lines[0]).toContain(repo.split("/").pop());
    expect(lines[1]).toContain("OMC");
  } finally {rmSync(repo,{recursive:true,force:true});}
});

test("task 668: bad settings.json retains valid legacy HUD fallback", () => {
  const home=process.env.HOME!;
  mkdirSync(join(home,".claude",".omc"),{recursive:true});
  writeFileSync(join(home,".claude",".omc","hud-config.json"),
    JSON.stringify({preset:"focused",elements:{cwd:true},thresholds:{}}));
  writeFileSync(join(home,".claude","settings.json"),"{not valid JSON");
  const config:any=readHudConfig();
  expect(config.elements.cwd).toBe(true);
});

test("task 668: configured Git elements do not crash outside a Git repository", async () => {
  const empty=mkdtempSync(join(tmpdir(),"issue668-nogit-"));
  try {
    const config:any={...DEFAULT_HUD_CONFIG,preset:"focused",
      elements:{...DEFAULT_HUD_CONFIG.elements,gitRepo:true,gitBranch:true,
        cwd:false,omcLabel:true,rateLimits:false,agents:false,maxOutputLines:6}};
    const ctx:any={cwd:empty,activeAgents:[],todos:[],backgroundTasks:[]};
    expect(await render(ctx,config)).toContain("OMC");
  } finally {rmSync(empty,{recursive:true,force:true});}
});

''',
 8152: r'''import { test, expect, vi, beforeEach, afterEach } from "vitest";
import { join } from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";
const st = vi.hoisted(() => ({
  handlers: {} as Record<string,(context:any)=>Promise<void>>,
  getFile: vi.fn(async () => ({ file_path: "voice.ogg" })),
  sendMessage: vi.fn(async () => undefined),
  sendChatAction: vi.fn(async () => undefined)
}));
vi.mock("grammy", () => ({
  Bot: class {
    api = { getFile: st.getFile, sendMessage: st.sendMessage, sendChatAction: st.sendChatAction };
    constructor(_token: string) {}
    command(_cmd: string, _handler: any) {}
    on(evt: string, fn: any) { st.handlers[evt] = fn; }
    catch(_fn: any) {}
    start() { return Promise.resolve(); }
    stop() { return Promise.resolve(); }
  }
}));
vi.mock("../utils/settings", () => ({
  loadUserSettings: () => ({ telegram: {} }),
  resolveTelegramStreamSettings: () => ({ streaming: "off", typingIndicator: false })
}));
vi.mock("./typing-refresh", () => ({
  startTypingRefresh: () => () => undefined
}));
import { createTelegramBridge } from "./bridge.js";
const origFetch = globalThis.fetch;
const origOpenAI = process.env.OPENAI_API_KEY;
const origLocal = process.env.GROK_TELEGRAM_TRANSCRIBER;
beforeEach(() => {
  st.handlers = {};
  const bin = join(process.env.HOME!, "voice-transcriber-fixture");
  mkdirSync(process.env.HOME!, { recursive: true });
  writeFileSync(bin, "#!/usr/bin/env node\nprocess.stdin.resume(); process.stdin.on('end', () => { process.stdout.write('voice text accepted\\n'); });\n", { mode: 0o755 });
  process.env.GROK_TELEGRAM_TRANSCRIBER = bin;
  process.env.OPENAI_API_KEY = "REDACTED_CREDENTIAL";
  globalThis.fetch = vi.fn(async (url: any) => {
    const u = String(url);
    if (u.includes("/file/bot")) return {
      ok: true, status: 200, arrayBuffer: async () => new Uint8Array([1,2,3]).buffer
    } as any;
    if (u.includes("/audio/transcriptions")) return {
      ok: true, status: 200, json: async () => ({ text: "voice text accepted" })
    } as any;
    throw new Error("Unexpected external request blocked by offline acceptance mock: "+u);
  }) as any;
});
afterEach(() => {
  globalThis.fetch = origFetch;
  if (origOpenAI===undefined) delete process.env.OPENAI_API_KEY; else process.env.OPENAI_API_KEY = origOpenAI;
  if (origLocal===undefined) delete process.env.GROK_TELEGRAM_TRANSCRIBER; else process.env.GROK_TELEGRAM_TRANSCRIBER = origLocal;
});
function makeBridge(approved:number[]) {
  const observed:string[]=[];
  createTelegramBridge({
    token: "FAKE_TELEGRAM_TOKEN_NOT_VALID",
    getApprovedUserIds: () => approved,
    coordinator: { run: async (fn:()=>Promise<void>) => await fn() } as any,
    getTelegramAgent: () => ({
      processMessage: async function* (_text: string) { yield { type: "content", content: "OK" }; }
    }) as any,
    onUserMessage: ({ content }) => observed.push(content)
  });
  return observed;
}
function makeVoiceContext() {
  const reply = vi.fn(async (_text:string)=>undefined);
  return { from: { id: 42 }, chat: { id: 7 },
    message: { message_id: 99, voice: { file_id: "offline-voice-id", file_size: 3 } },
    getFile: async () => ({ file_path: "voice.ogg" }), reply };
}
test("task 8152: Telegram voice messages are registered, transcribed and passed to the agent", async () => {
  const observed=makeBridge([42]);
  expect(typeof st.handlers["message:voice"]).toBe("function");
  const ctx=makeVoiceContext();
  await st.handlers["message:voice"](ctx);
  expect(observed).toContain("voice text accepted");
  expect(ctx.reply).not.toHaveBeenCalledWith(expect.stringContaining("Not paired"));
});
test("task 8152: unapproved voice sender cannot reach download/transcription", async () => {
  const observed=makeBridge([]);
  expect(typeof st.handlers["message:voice"]).toBe("function");
  const ctx=makeVoiceContext();
  await st.handlers["message:voice"](ctx);
  expect(observed).toEqual([]);
  expect(globalThis.fetch).not.toHaveBeenCalled();
  expect(ctx.reply).toHaveBeenCalledWith(expect.stringContaining("Not paired"));
});
'''
}
PATHS={668:"src/__tests__/phase2_668_acceptance.test.ts",8152:"src/telegram/phase2_8152_acceptance.test.ts"}
