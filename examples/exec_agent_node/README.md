# `exec:` runner reference — Node.js

A ~50-line, zero-dependency [`whatifd-exec/1`](../../docs/runner-contract-exec.md)
runner in Node.js. It is the concrete proof that whatifd's runner contract is
language-agnostic: any language that can read/write line-buffered JSON on
stdio can be a whatifd runner, no SDK required.

## Validate it

```bash
whatifd exec-check "exec:node examples/exec_agent_node/agent.js"
```

Expected:

```
  ok  handshake — runner exec-agent-node v1.0.0 (whatifd-exec/1)
  ok  replay — got ReplayOutput (text N chars, 0 tool span(s))
  ok  shutdown
whatifd exec-check: runner conforms to whatifd-exec/1.
```

## Use it as a runner

```yaml
# whatifd.config.yaml
target:
  runner: "exec:node examples/exec_agent_node/agent.js"
```

## What it does

1. **Handshake** — sends `hello` (`protocol: whatifd-exec/1`, plus
   `runner_name`/`runner_version`), waits for `hello_ack`.
2. **Replay loop** — for each `replay_request`, returns a `replay_response`
   whose `output` mirrors `ReplayOutput` (`text`, `tool_spans`, `metadata`).
   If the prompt mentions a tool, it issues a `tool_lookup` and whatifd's
   parent answers from the canonical tool cache (cache keying stays in core).
3. **Shutdown** — exits cleanly on the `shutdown` frame.

Swap the body of the replay loop for a call into your real agent; the protocol
plumbing stays the same. See `docs/runner-contract-exec.md` for the wire
contract, failure mapping, and report/manifest additions.
