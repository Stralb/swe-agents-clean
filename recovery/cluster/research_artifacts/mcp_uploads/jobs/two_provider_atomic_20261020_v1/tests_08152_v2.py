def modify(repo):
 p=repo/'src/telegram/voice.test.ts'
 t=p.read_text()
 edits=[
 ("transcribeTelegramVoice, validateTelegramFilePath","transcribeTelegramVoice, validateTelegramDownloadUrl, validateTelegramFilePath"),
 ("url.includes('api.telegram.org')","new URL(url).hostname === 'api.telegram.org'"),
 ("transcribeTelegramVoice({ botToken: 'test-token', filePath: 'voice/x.ogg'","transcribeTelegramVoice({ downloadUrl: 'https://api.telegram.org/file/bottest-token/voice/x.ogg'"),
 ("transcribeTelegramVoice({ botToken: 'token', filePath: 'voice/x.ogg'","transcribeTelegramVoice({ downloadUrl: 'https://api.telegram.org/file/bottoken/voice/x.ogg'")
 ]
 for a,b in edits:
  assert t.count(a)==1,(a,t.count(a))
  t=t.replace(a,b,1)
 anchor="    expect(validateTelegramFilePath('voice/file_1.oga')).toBe('voice/file_1.oga');"
 extras="""    expect(validateTelegramDownloadUrl('https://api.telegram.org/file/bottest/voice/x.ogg').hostname).toBe('api.telegram.org');
    expect(() => validateTelegramDownloadUrl('https://api.telegram.org.evil.test/file/bottest/voice/x.ogg')).toThrow();
    expect(() => validateTelegramDownloadUrl('http://api.telegram.org/file/bottest/voice/x.ogg')).toThrow();
    expect(() => validateTelegramDownloadUrl('https://api.telegram.org/file/bottest/%2Fetc')).toThrow();"""
 assert t.count(anchor)==1
 p.write_text(t.replace(anchor,anchor+'\n'+extras,1))
