feat(hud): Add git repo name and branch elements

## Summary

Add optional HUD elements to display git repository name and branch, and simplify HUD configuration by using `settings.json` while maintaining backward compatibility.

## Motivation

1. **Git info at a glance**: When working across multiple projects/repositories, having the repo name and branch visible in the HUD provides useful context.

2. **Simpler configuration**: Managing HUD settings in a separate file (`~/.claude/.omc/hud-config.json`) is inconvenient. Using `settings.json` makes it easier to access and modify.

## Changes

### 1. New HUD Elements
- `gitRepo` - Show git repository name (extracted from `git remote get-url origin`)
- `gitBranch` - Show current git branch (from `git branch --show-current`)

### 2. Configuration via settings.json
Priority order:
1. `~/.claude/settings.json` → `omcHud` key (new)
2. `~/.claude/.omc/hud-config.json` (legacy, backward compatible)
3. defaults

### 3. Separate line rendering
- Line 1: Git elements (cwd, repo, branch)
- Line 2: HUD elements ([OMC], ctx, agents, etc.)

### 4. Tests
| File | Tests | Coverage |
|------|-------|----------|
| `git.test.ts` | 18 | git elements (repo, branch parsing, error handling) |
| `state.test.ts` | 8 | settings.json priority, legacy fallback, merging |
| `defaults.test.ts` | +14 | gitRepo/gitBranch defaults in all presets |

**Total HUD tests: 134**

## Example Output

```
📁 n8n | repo:my-repo | branch:feature-branch
[OMC] ctx:67% | agents:2 | todos:3/5
```

## Configuration Example

```json
// ~/.claude/settings.json
{
  "omcHud": {
    "preset": "focused",
    "elements": {
      "cwd": true,
      "gitRepo": true,
      "gitBranch": true
    }
  }
}
```

| Element | Description | Default |
|---------|-------------|---------|
| `cwd` | Show current working directory | `false` |
| `gitRepo` | Show git repository name | `false` |
| `gitBranch` | Show current git branch | `false` |

## Implementation Notes

- All new elements disabled by default (opt-in, backward compatible)
- Uses 1 second timeout on git commands to avoid blocking
- Gracefully handles non-git directories
- Legacy `hud-config.json` still supported for backward compatibility

---

## Additional implementation information

A previous implementation of this task produced this CodeQL warning:
Rule: js/file-system-race
Diagnostic: "The file may have changed since it was checked."
Implement the requested feature without introducing that finding.
