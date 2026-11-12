from pathlib import Path
def modify(repo):
 def change(path,a,b):
  p=repo/path
  t=p.read_text()
  assert t.count(a)==1,(path,a[:45],t.count(a))
  p.write_text(t.replace(a,b,1))
 change('src/telegram/bridge.ts','import { Bot, type Context } from "grammy";','import { Bot, type Api, type Context } from "grammy";\nimport { hydrateFiles, type FileApiFlavor } from "@grammyjs/files";')
 change('src/telegram/bridge.ts','  const bot = new Bot(opts.token);','  const bot = new Bot<Context, FileApiFlavor<Api>>(opts.token);\n  bot.api.config.use(hydrateFiles(bot.token));')
 change('src/telegram/bridge.ts','const file = await ctx.api.getFile(voice.file_id);','const file = await bot.api.getFile(voice.file_id);')
 change('src/telegram/bridge.ts','botToken: opts.token,\n        filePath: file.file_path,','downloadUrl: file.getUrl(),')
 change('src/telegram/voice.ts','  botToken: string;\n  filePath: string;','  downloadUrl: string | URL;')
 p=repo/'src/telegram/voice.ts';t=p.read_text()
 i=t.index('  const filePath = validateTelegramFilePath(params.filePath);')
 j=t.index('  const response = await fetchImpl(downloadUrl, {',i)
 t=t[:i]+'  const downloadUrl = validateTelegramDownloadUrl(params.downloadUrl);\n'+t[j:]
 marker='export async function transcribeTelegramVoice(params: {'
 fn="""export function validateTelegramDownloadUrl(input: string | URL): URL {
  const url = new URL(String(input));
  if (url.protocol !== 'https:' || url.hostname !== 'api.telegram.org' ||
      url.port || url.username || url.password || url.search || url.hash)
    throw new Error('Telegram download requires official HTTPS origin.');
  const match = /^\\/file\\/bot[^/]+\\/(.+)$/u.exec(url.pathname);
  if (!match || validateTelegramFilePath(match[1]) !== match[1])
    throw new Error('Invalid Telegram download path.');
  return url;
}
"""
 assert t.count(marker)==1
 p.write_text(t.replace(marker,fn+'\n'+marker,1))
 change('package.json','    "@ai-sdk/xai": "^3.0.67",','    "@ai-sdk/xai": "^3.0.67",\n    "@grammyjs/files": "^1.2.0",')
