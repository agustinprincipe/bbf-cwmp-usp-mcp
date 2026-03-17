---
name: setup-statusline
description: Configure the statusline monitor in your Claude Code settings
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Setup Statusline Monitor

Configure the Claude Code statusline to use the statusline-monitor plugin script.

## Steps

1. Read the user's current `~/.claude/settings.json`
2. Add or update the `statusLine` configuration to point to the plugin's script:

```json
"statusLine": {
  "type": "command",
  "command": "${CLAUDE_PLUGIN_ROOT}/scripts/statusline.js"
}
```

3. Write the updated settings back
4. Inform the user they need to restart Claude Code for the change to take effect

## Important

- Preserve all existing settings — only add/update the `statusLine` key
- If a `statusLine` is already configured, ask the user before overwriting
- The script path MUST use `${CLAUDE_PLUGIN_ROOT}` for portability
