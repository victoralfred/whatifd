#!/usr/bin/env node
// Reference `whatifd-exec/1` runner in Node.js — zero dependencies, ~50 lines.
//
// This is the "implement the runner contract in any language" proof: it speaks
// the same line-buffered NDJSON protocol the Python `exec:` lane drives. See
// `docs/runner-contract-exec.md` for the full contract.
//
// Use it as a whatifd runner target:
//   target:
//     runner: "exec:node examples/exec_agent_node/agent.js"
// or validate it directly:
//   whatifd exec-check "exec:node examples/exec_agent_node/agent.js"
'use strict';
const readline = require('readline');

function send(obj) {
  // One JSON object per newline-terminated line.
  process.stdout.write(JSON.stringify(obj) + '\n');
}

// Minimal request/response queue over stdin: callers `await recv()` for the
// next frame; lines that arrive early are buffered.
const queue = [];
let pending = null;
readline.createInterface({ input: process.stdin }).on('line', (line) => {
  let frame;
  try {
    frame = JSON.parse(line);
  } catch {
    return; // ignore non-JSON noise; stderr is the free log channel
  }
  if (pending) {
    const resolve = pending;
    pending = null;
    resolve(frame);
  } else {
    queue.push(frame);
  }
});
const recv = () =>
  new Promise((resolve) => (queue.length ? resolve(queue.shift()) : (pending = resolve)));

async function main() {
  // 1. Handshake — the child speaks first.
  send({
    v: 1,
    type: 'hello',
    protocol: 'whatifd-exec/1',
    runner_name: 'exec-agent-node',
    runner_version: '1.0.0',
    capabilities: [],
  });
  await recv(); // hello_ack

  // 2. Replay loop — one replay_response per replay_request.
  for (;;) {
    const f = await recv();
    if (!f || f.type === 'shutdown') break;
    const rid = f.request_id;
    const msg = (f.trace_input && f.trace_input.user_message) || '';

    // Demo: if the prompt mentions a tool, ask whatifd's cache (keying stays
    // in the parent — the child never computes cache keys).
    let toolNote = '';
    if (msg.includes('tool')) {
      send({
        v: 1,
        type: 'tool_lookup',
        request_id: rid,
        lookup_id: 'L1',
        tool_name: 'search',
        args: { q: 'whatifd-exec-check' },
      });
      const tr = await recv();
      toolNote = ` (tool hit=${tr.hit})`;
    }

    send({
      v: 1,
      type: 'replay_response',
      request_id: rid,
      output: { text: `node replayed: ${msg}${toolNote}`, tool_spans: [], metadata: {} },
    });
  }
  process.exit(0);
}

main();
