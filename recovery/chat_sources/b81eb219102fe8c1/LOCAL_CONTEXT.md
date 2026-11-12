# BOUNDED PRE-CHANGE IMPLEMENTATION CONTEXT

Target: `src/RevealServer.ts`

`RevealServer` configures an Express application for a presentation. The root request renders `index` using the parsed slides and presentation configuration.

Relevant structure:

```ts
import * as http from 'http'
import express from 'express'
import ejs from 'ejs'
import cors from 'cors'
import morgan from 'morgan'
import * as path from 'path'

export class RevealServer extends Disposable {
  public readonly app = express()

  constructor(private readonly context: RevealContext) {
    super()
    this.configure()
  }

  private configure() {
    const app = this.app
    const context = this.context

    // middleware and static-file setup omitted

    app.use((req, res, next) => {
      if (req.path !== '/') {
        next()
      } else {
        let init: string | null = null
        let initModule = false

        // Existing repository init-file loading code occurs here.
        // Its body is intentionally not included in this bounded packet.

        setDiagramRenderingConfig({
          enabled: context.configuration.diagramServerEnabled,
          serverBaseUrl: context.configuration.diagramServerUrl,
        })

        const htmlSlides = context.slides.map((s) => ({
          ...s,
          html: markdownit.render(s.text),
          children: s.verticalChildren.map((c) => ({
            ...c,
            html: markdownit.render(c.text),
          })),
        }))

        res.render('index', {
          slides: htmlSlides,
          ...context.configuration,
          rootUrl: this.uri,
          init,
          initModule,
          jsonForScript,
        })
      }
    })
  }
}
```

Implement only the server-side `htmlFragment` loading/injection portion needed by the issue. You may add imports or small helper methods in `RevealServer.ts`.
