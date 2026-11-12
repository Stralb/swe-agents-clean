# AUTHENTIC PRE-EXISTING REPOSITORY CONTEXT

The following code existed in the repository before the task's historical implementation.

```text
// Check if already authenticated
    const username = sessionStorage.getItem('mqtt-explorer-username')
    const password = sessionStorage.getItem('mqtt-explorer-password')

    if (username && password) {
      // Try to use stored credentials
      setIsAuthenticated(true)
    } else {
      // Show login dialog
      setShowLogin(true)
    }
  }, [])

  const handleLogin = async (username: string, password: string) => {
    try {
      // Store credentials in session storage
      sessionStorage.setItem('mqtt-explorer-username', username)
      sessionStorage.setItem('mqtt-explorer-password', password)

      // The socket will use these credentials on next connection
      setIsAuthenticated(true)
      setShowLogin(false)
      setLoginError(undefined)

      // Reload to reinitialize socket with new auth
      window.location.reload()
    } catch (error) {
      setLoginError('Login failed. Please check your credentials.')
    }
  }
```
