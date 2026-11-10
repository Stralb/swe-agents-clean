# AUTHENTIC PRE-EXISTING REPOSITORY CONTEXT

The following code existed in the repository before the task's historical implementation.

```text
let init: string | null = null
        let initModule = false
        if (context.dirname) {
          const initModulePath = path.join(context.dirname, 'init.esm.js')
          const initPath = path.join(context.dirname, 'init.js')
          if (fs.existsSync(initModulePath)) {
            init = 'init.esm.js'
            initModule = true
          } else if (fs.existsSync(initPath)) {
            init = fs.readFileSync(initPath, 'utf8')
          }
        }
```
