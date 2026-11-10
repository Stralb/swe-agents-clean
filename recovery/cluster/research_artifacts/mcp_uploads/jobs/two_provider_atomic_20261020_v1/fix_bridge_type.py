from pathlib import Path
p=Path.home()/'research_artifacts/prevention_pilot_phase2/provider_variants_20261020/08152/baseline/REPO/src/telegram/bridge.ts'
s=p.read_text();a=s.index('  const handleText =');b=s.index('  bot.on("message:text"',a)
t=s[a:b];t=t.replace('if (!ctx.message) return;','const chat = ctx.chat;\n    const message = ctx.message;\n    if (!chat || !message) return;')
t=t.replace('ctx.chat.','chat.').replace('ctx.message.','message.')
p.write_text(s[:a]+t+s[b:])
