def modify(repo):
 p=repo/'src/telegram/voice.test.ts'
 t=p.read_text()
 def replace(a,b):
  nonlocal t
  assert t.count(a)==1,(a[:40],t.count(a))
  t=t.replace(a,b,1)
 replace("transcribeTelegramVoice, validateTelegramFilePath","transcribeTelegramVoice, validateTelegramDownloadUrl, validateTelegramFilePath")
 replace("url.includes('api.telegram.org')","new URL(url).hostname === 'api.telegram.org'")
 replace("transcribeTelegramVoice({ botToken: 'test-token', filePath: 'voice/x.ogg'","transcribeTelegramVoice({ downloadUrl: 'https://api.telegram.org/file/bottest-token/voice/x.ogg'")
 replace("transcribeTelegramVoice({ botToken: 'token', filePath: 'voice/x.ogg'","transcribeTelegramVoice({ downloadUrl: 'https://api.telegram.org/file/bottoken/voice/x.ogg'")
 anchor="    expect(validateTelegramFilePath('voice/file_1.oga')).toBe('voice/file_1.oga');"
 insert="""    expect(validateTelegramDownloadUrl('https://api.telegram.org/file/bottest/voice/x.ogg').hostname).toBe('api.telegram.org');
    expect(() => validateTelegramDownloadUrl('https://api.telegram.org.evil.test/file/bottest/voice/x.ogg')).toThrow();
    expect(() => validateTelegramDownloadUrl('http://api.telegram.org/file/bottest/voice/x.ogg')).toThrow();
    expect(() => validateTelegramDownloadUrl('https://api.telegram.org/file/bottest/../other')).toThrow();"""
 replace(anchor,anchor+'\n'+insert)
 p.write_text(t)
