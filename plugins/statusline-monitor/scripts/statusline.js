#!/usr/bin/env node
// Claude Code Statusline - Context & Usage Monitor
// Shows: model | task | dir | context bar | tokens | 5hr usage | 7day usage | cost | duration

const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');

// ANSI codes
const DIM = '\x1b[2m';
const BOLD = '\x1b[1m';
const RESET = '\x1b[0m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const ORANGE = '\x1b[38;5;208m';
const RED_FLASH = '\x1b[5;31m';

const CACHE_PATH = path.join(os.tmpdir(), 'claude-statusline-usage.json');
const CACHE_MAX_AGE_S = 60;

function colorForPct(pct) {
  if (pct >= 80) return RED_FLASH;
  if (pct >= 65) return ORANGE;
  if (pct >= 50) return YELLOW;
  return GREEN;
}

function makeBar(pct, width = 8) {
  const filled = Math.round((pct / 100) * width);
  return '▓'.repeat(filled) + '░'.repeat(width - filled);
}

function formatResetTime(isoStr) {
  if (!isoStr) return '';
  const reset = new Date(isoStr);
  const now = new Date();
  const diffMs = reset - now;
  if (diffMs <= 0) return 'now';

  const diffH = Math.floor(diffMs / 3600000);
  const diffM = Math.floor((diffMs % 3600000) / 60000);

  if (diffH >= 24) {
    const days = Math.floor(diffH / 24);
    const hrs = diffH % 24;
    return `${days}d${hrs}h`;
  }
  if (diffH > 0) return `${diffH}h${diffM}m`;
  return `${diffM}m`;
}

function readCachedUsage() {
  try {
    const stat = fs.statSync(CACHE_PATH);
    const ageS = (Date.now() - stat.mtimeMs) / 1000;
    if (ageS <= CACHE_MAX_AGE_S) {
      return JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    }
  } catch {}
  return null;
}

function fetchUsage() {
  return new Promise((resolve) => {
    try {
      const claudeDir = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
      const credsPath = path.join(claudeDir, '.credentials.json');
      const creds = JSON.parse(fs.readFileSync(credsPath, 'utf8'));
      const token = creds?.claudeAiOauth?.accessToken;
      if (!token) return resolve(null);

      const req = https.request('https://api.anthropic.com/api/oauth/usage', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'anthropic-beta': 'oauth-2025-04-20',
          'Content-Type': 'application/json',
        },
        timeout: 3000,
      }, (res) => {
        let body = '';
        res.on('data', (c) => body += c);
        res.on('end', () => {
          try {
            const data = JSON.parse(body);
            fs.writeFileSync(CACHE_PATH, JSON.stringify(data), 'utf8');
            resolve(data);
          } catch { resolve(null); }
        });
      });
      req.on('error', () => resolve(null));
      req.on('timeout', () => { req.destroy(); resolve(null); });
      req.end();
    } catch { resolve(null); }
  });
}

async function getUsage() {
  const cached = readCachedUsage();
  if (cached) return cached;
  return fetchUsage();
}

function formatUsageSegment(label, data) {
  if (!data || data.utilization == null) return '';
  const pct = Math.round(data.utilization);
  const color = colorForPct(pct);
  const bar = makeBar(pct);
  const reset = formatResetTime(data.resets_at);
  const resetStr = reset ? ` ${DIM}~${reset}${RESET}` : '';
  return `${DIM}${label}${RESET} ${color}${bar} ${pct}%${RESET}${resetStr}`;
}

function formatTokens(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

let input = '';
const stdinTimeout = setTimeout(() => process.exit(0), 5000);
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  clearTimeout(stdinTimeout);
  try {
    const data = JSON.parse(input);
    const model = data.model?.display_name || 'Claude';
    const dir = data.workspace?.current_dir || process.cwd();
    const session = data.session_id || '';
    const remaining = data.context_window?.remaining_percentage;
    const totalIn = data.context_window?.total_input_tokens || 0;
    const totalOut = data.context_window?.total_output_tokens || 0;
    const cost = data.cost?.total_cost_usd || 0;
    const durationMs = data.cost?.total_duration_ms || 0;

    // Context window display — normalize against autocompact buffer
    const AUTO_COMPACT_BUFFER_PCT = 16.5;
    let ctx = '';
    if (remaining != null) {
      const usableRemaining = Math.max(0, ((remaining - AUTO_COMPACT_BUFFER_PCT) / (100 - AUTO_COMPACT_BUFFER_PCT)) * 100);
      const used = Math.max(0, Math.min(100, Math.round(100 - usableRemaining)));
      const bar = makeBar(used, 10);
      const color = colorForPct(used);
      const prefix = used >= 80 ? '💀 ' : '';
      ctx = `${color}${prefix}${bar} ${used}%${RESET}`;
    }

    // Current task from todos
    let task = '';
    const claudeDir = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
    const todosDir = path.join(claudeDir, 'todos');
    if (session && fs.existsSync(todosDir)) {
      try {
        const files = fs.readdirSync(todosDir)
          .filter(f => f.startsWith(session) && f.endsWith('.json'))
          .map(f => ({ name: f, mtime: fs.statSync(path.join(todosDir, f)).mtime }))
          .sort((a, b) => b.mtime - a.mtime);
        if (files.length > 0) {
          const todos = JSON.parse(fs.readFileSync(path.join(todosDir, files[0].name), 'utf8'));
          const inProgress = todos.find(t => t.status === 'in_progress');
          if (inProgress) task = inProgress.activeForm || inProgress.subject || '';
        }
      } catch {}
    }

    // Cost and duration
    const costStr = `$${cost.toFixed(2)}`;
    const mins = Math.floor(durationMs / 60000);
    const secs = Math.floor((durationMs % 60000) / 1000);
    const timeStr = `${mins}m ${secs}s`;

    // Fetch usage data (cached, non-blocking)
    const usage = await getUsage();

    // Build output
    const dirname = path.basename(dir);
    const parts = [`${DIM}${model}${RESET}`];
    if (task) parts.push(`${BOLD}${task}${RESET}`);
    parts.push(`${DIM}${dirname}${RESET}`);
    if (ctx) parts.push(ctx);

    // Session token usage
    if (totalIn > 0 || totalOut > 0) {
      parts.push(`${DIM}↑${formatTokens(totalIn)} ↓${formatTokens(totalOut)}${RESET}`);
    }

    // Usage limits
    if (usage) {
      const fiveHr = formatUsageSegment('5h', usage.five_hour);
      const sevenDay = formatUsageSegment('7d', usage.seven_day);
      if (fiveHr) parts.push(fiveHr);
      if (sevenDay) parts.push(sevenDay);
    }

    parts.push(`${DIM}${costStr}${RESET}`);
    parts.push(`${DIM}${timeStr}${RESET}`);

    process.stdout.write(parts.join(' │ '));
  } catch {}
});
