---
name: remove-statusline
description: Remove the statusline monitor from your Claude Code settings
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Remove Statusline Monitor

Remove the statusline-monitor configuration from Claude Code settings.

## Steps

1. Read `~/.claude/settings.json`
2. Remove the `statusLine` key if it exists
3. Write the updated settings back
4. Inform the user they need to restart Claude Code for the change to take effect