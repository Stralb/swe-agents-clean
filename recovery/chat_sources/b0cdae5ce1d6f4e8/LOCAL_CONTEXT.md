# BOUNDED PRE-CHANGE IMPLEMENTATION CONTEXT

The task is localized to the browser-mode websocket IPC authentication path.

Relevant pre-change pieces:

`LoginDialog` supplies credentials to its parent:

```ts
interface LoginDialogProps {
  open: boolean
  onLogin: (username: string, password: string) => void
  error?: string
}
```

The browser event bus uses Socket.IO and supplies credentials through the socket `auth` object:

```ts
const socket = io({
  auth: {
    username,
    password,
  },
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: Infinity,
  transports: ['websocket', 'polling'],
})
```

`BrowserAuthWrapper` owns login UI state:

```ts
export function BrowserAuthWrapper(props: BrowserAuthWrapperProps) {
  const [isAuthenticated, setIsAuthenticated] = React.useState(false)
  const [loginError, setLoginError] = React.useState<string | undefined>()
  const [showLogin, setShowLogin] = React.useState(false)

  // Existing credential-lifecycle implementation is intentionally
  // not included in this bounded packet.

  const handleLogin = async (username: string, password: string) => {
    // implementation to be adapted as part of the browser IPC/auth work
  }
}
```

Implement the browser IPC/authentication portion of the security-review task. Keep the public login callback shape compatible with `LoginDialog` and preserve reconnect behavior.
