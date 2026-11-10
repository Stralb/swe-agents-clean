#!/usr/bin/env python3
"""Exploratory per-design adapter. NOT an architecture-blind confirmatory evaluator."""
TEST = r'''import { test, expect, vi } from "vitest";
import fs from "node:fs/promises";
import path from "node:path";
import { resolveSessionArtifactsDir } from "../../src/browser/artifacts.js";
import * as candidate from "../../src/browser/chatgptFiles.js";
const href="sandbox:/mnt/data/source.zip";
const firstParty="https://chatgpt.com/backend-api/files/source.zip";
const payload=Buffer.from("TEST_ZIP_FIXTURE");
test("Issue 22223: a generic sandbox ZIP is saved and exposed as a session file artifact", async () => {
  const sessionId="phase2-generic-zip";
  const dir=resolveSessionArtifactsDir(sessionId);
  let downloadPath="";
  const Runtime:any = {
    evaluate: vi.fn(async (args:any) => {
      if (String(args.expression).includes("link.click")) {
        if (!downloadPath) throw new Error("download directory was not configured");
        await fs.writeFile(path.join(downloadPath, "downloaded.zip"),payload);
        return {result:{value:true}};
      }
      return {result:{value:[{raw:href,resolved:firstParty,href,label:"Source ZIP"}]}};
    })
  };
  const Page:any = {
    setDownloadBehavior: vi.fn(async (args:any) => {
      if (args.behavior==="allow")downloadPath=args.downloadPath;
    })
  };
  const Network:any = {
    getCookies: vi.fn(async () => ({cookies:[]}))
  };
  const originalFetch=globalThis.fetch;
  globalThis.fetch=vi.fn(async (url:any) => {
    if (String(url)!==firstParty)throw new Error("Unexpected network endpoint "+String(url));
    return new Response(payload,{status:200,headers:{"content-type":"application/zip","content-length":String(payload.length)}});
  }) as any;
  try {
    let artifacts:any[];
    const api:any=candidate;
    if (typeof api.saveChatGptFileArtifacts==="function") {
      artifacts=await api.saveChatGptFileArtifacts({
        answerMarkdown:"[Source ZIP]("+href+")",Runtime,Network,sessionId
      });
    } else if (typeof api.collectChatGptDownloadArtifacts==="function") {
      artifacts=await api.collectChatGptDownloadArtifacts({Runtime,Page,sessionId});
    } else {
      throw new Error("Candidate does not expose a generic browser-download collector");
    }
    expect(artifacts.length).toBe(1);
    expect(artifacts[0].kind).toBe("file");
    expect(path.resolve(artifacts[0].path).startsWith(path.resolve(dir)+path.sep)).toBe(true);
    expect(await fs.readFile(artifacts[0].path)).toEqual(payload);
    expect(artifacts[0].sizeBytes).toBe(payload.length);
  } finally {
    globalThis.fetch=originalFetch;
    await fs.rm(dir,{recursive:true,force:true});
  }
});
'''
REL="tests/browser/phase2_22223_generic_file_smoke.test.ts"
