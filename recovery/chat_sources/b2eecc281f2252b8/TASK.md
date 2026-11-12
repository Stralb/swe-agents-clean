[Bug]: Session stack on image too big

### Bug type

Crash or hang

### Summary

I'm developing an app and gsd is taking screenshots to check for correct rendering. Everything worked for a few days, then apparently the last screenshot generated an image that is too big to process, and the session is stuck on a "Error: 400", without options to skip the error and continue.

### Steps to reproduce

--

### Expected behavior

GSD should either allow skipping the error and move on, or try the screenshot tool differently.

### Actual behavior

GSD session is stuck. Starting a new session is possible but lose all the context.

### GSD version

2.54.0

### Node.js version

v22.20.0

### Operating system

macOS

### Install method

npm global install

### Affected area

Auto-mode / dispatch loop

### Model and provider

anthropic/claude-opus-4-6

### Logs, screenshots, and evidence

```shell
Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"messages.125.content.38.image.source.base64.data: At least one of the image dimensions exceed max
 allowed size for many-image requests: 2000 pixels"},"request_id":"req_..."}
 2026-03-26 19:25
                                                                                                                                                                    2026-03-27 11:30


 continue/retry


 Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"messages.125.content.38.image.source.base64.data: At least one of the image dimensions exceed max
 allowed size for many-image requests: 2000 pixels"},"request_id":"req_..."}
 2026-03-27 11:30
                                                                                                                                                                    2026-03-27 11:39


 you're stuck because the screenshot is too big


 Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"messages.125.content.38.image.source.base64.data: At least one of the image dimensions exceed max
 allowed size for many-image requests: 2000 pixels"},"request_id":"req_..."}
 2026-03-27 11:39
                                                                                                                                                                    2026-03-27 11:39


 skip the image


 Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"messages.131.content.59.image.source.base64.data: At least one of the image dimensions exceed max
 allowed size for many-image requests: 2000 pixels"},"request_id":"req_..."}
 2026-03-27 11:39
                                                                                                                                                                    2026-03-27 11:40


 help


 Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"messages.129.content.39.image.source.base64.data: At least one of the image dimensions exceed max
 allowed size for many-image requests: 2000 pixels"},"request_id":"req_..."}
 2026-03-27 11:40
```

### Impact

_No response_

### Additional information

_No response_
