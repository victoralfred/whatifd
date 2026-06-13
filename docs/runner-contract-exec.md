# Runner contract over stdio — the `exec:` scheme (`whatifd-exec/1`)

> **Status:** ACCEPTED spec (promoted 2026-06-13, autopilot cycle 2). This is
> the contract the `exec:` lane implements; the design questions formerly in §9
> are now settled (see §9). Implementation follows in its own sub-PR(s) per the
> doctrine-guarded "spec first, implementation second" discipline; the design
> record + the load-bearing integration decision (subprocess lifetime vs the
> per-trace `Runner` protocol) live in
> `whatifd-design/references/cascade-catalog.md` ("exec: runner lane").
>
> **Lineage:** written 2026-06-13 against `src/whatifd/contract/__init__.py`,
> `src/whatifd/runner_loader.py`, and `docs/runner-contract.md` at `main`
> @ 47869c1 (v0.3.0). Wire shapes below mirror the Pydantic models *by field
> name*; any divergence is a spec bug.

---

## 1. Problem and goal

The runner is whatifd's only user-facing extension point, and today
`runner_loader.py` accepts exactly one scheme — `python:<module.path>:<attr>`
(the loader's own error text: "v0.1 supports `python:<module.path>:<attr>`
only", `runner_loader.py:97-101`). That makes the smallest unit of adoption
"rewrite your agent's replay entry point in Python," which excludes the large
TypeScript/Go agent population.

**Goal:** a second scheme, `exec:<argv...>`, that runs the user's replay
entry point as a child process speaking a small NDJSON protocol over
stdin/stdout — so any language can satisfy the contract with ~50 lines and no
SDK. **Non-goals:** this is not MCP, not a network protocol, not token
streaming, not an agent runtime, and v1 deliberately excludes live tool calls
(the v0.3+ live-replay/allowlist work owns that; this spec is
`use-original`-only).

## 2. Design constraints inherited from the doctrine

1. **Single-sourced cache keying.** `ToolCache.lookup` canonicalizes
   `(tool_name, args)` via the same keying as `whatifd/cache/keying/v1.py`.
   Re-implementing that hash in every guest language guarantees silent
   drift — a reviewer-misleading bug class. Therefore the child **never
   computes cache keys**: tool-cache access is a *callback* over the same
   stdio stream, answered by the parent using the one true implementation.
2. **Defensible runner identity.** `python:` runners are identified by
   module path; the exec lane must record *what binary ran*. The handshake
   plus parent-side hashing feed `methodology`/`runtime` so a reviewer can
   answer "which runner produced this verdict?"
3. **Existing failure registry first.** Protocol failures map onto the
   shipped `failures[].code` registry (`runner_timeout`, `runner_exception`)
   with one proposed addition (`runner_protocol_error`) rather than a
   parallel error system.
4. **Sensitive content note.** `ToolSpan.input/output` are `Sensitive[str]`
   in-process; on this wire they serialize as plain strings. The wire is a
   process-local pipe between two components of the same trust domain;
   redaction remains a *render-time* property, unchanged. State this rather
   than pretend the pipe is encrypted.

## 3. Scheme grammar and process model

```yaml
target:
  runner: "exec:./replay-agent --mode whatifd"   # argv split shell-style (POSIX rules; no shell interpolation)
  # python:-scheme unchanged and still the default documentation path
```

- Parent resolves `argv[0]` against PATH/cwd, records the absolute path and
  its sha256 in the run manifest, and spawns the child once per **session**
  (persistent mode is the only mode; "oneshot" is just a session of length 1
  — one protocol, no mode flag).
- Pipes: parent→child on stdin, child→parent on stdout, both line-buffered
  UTF-8 NDJSON (exactly one JSON object per `\n`-terminated line; no frame
  may contain a raw newline — JSON string escaping handles content).
  **stderr is the child's free log channel**, captured to whatifd's debug log,
  never parsed.
- Child lifetime: parent sends `shutdown` after the last replay and waits
  `min(5s, replay_seconds)` before SIGTERM→SIGKILL. Child exit before
  `shutdown` ⇒ failure (see §6).

## 4. Wire messages

All frames carry `"v": 1` (protocol major) and `"type"`. Unknown *optional*
fields MUST be tolerated (mirrors the report schema's unknown-key rule);
unknown `type` from the child is a protocol error.

### 4.1 Handshake (child speaks first)

```json
{"v":1,"type":"hello","protocol":"whatifd-exec/1","runner_name":"acme-support-agent","runner_version":"2026.06.1","capabilities":[]}
```

Parent replies:

```json
{"v":1,"type":"hello_ack","whatifd_version":"0.4.0","session_id":"<uuid>","tool_cache_policy":"use-original"}
```

`runner_name`/`runner_version` + executable sha256 + argv are recorded for
the report (§7). A child whose first line is not a valid `hello` within 10s
fails the run at setup (no per-trace retries — the binary is broken).

### 4.2 Replay request (parent → child), one per selected trace

```json
{"v":1,"type":"replay_request","request_id":"r-000017",
 "trace_input":{"user_message":"...", "metadata":{...}},
 "replay_config":{"system_prompt":"new prompt or null","model":null,"overrides":{}}}
```

Field fidelity rules: `trace_input` carries exactly the `TraceInput` fields
(`user_message: str`, `metadata: object` — extra metadata keys preserved);
`replay_config` carries exactly `ReplayConfig` (`system_prompt`, `model`,
`overrides`), nulls meaning "fall back to your defaults", same semantics as
the Python lane. `request_id` is protocol-level correlation only — it is NOT
a contract field and MUST NOT be smuggled into outputs as a trace id.

### 4.3 Tool-cache callback (child → parent → child), zero or more per replay

```json
{"v":1,"type":"tool_lookup","request_id":"r-000017","lookup_id":"L1",
 "tool_name":"search_kb","args":{"query":"refund policy"}}
```

```json
{"v":1,"type":"tool_result","request_id":"r-000017","lookup_id":"L1",
 "hit":true,"output":"<original tool output as string, or structured JSON under \"output_json\">"}
```

- Parent answers via the canonical `ToolCache.lookup(tool_name, args)` —
  keying stays in core (constraint §2.1).
- `hit:false` means cache miss. The child decides whether it can proceed
  without the tool; if it cannot, it returns `replay_error` with
  `code:"tool_cache_miss"`, which the parent records as the existing
  `tool_cache_miss` failure (stage `replay`, scope `trace`). Under
  `use-original` policy the child MUST NOT substitute a live call; v1
  parents always declare `use-original` (§1 non-goals).
- Callbacks are serialized per request (child awaits each `tool_result`
  before the next `tool_lookup`); parents MAY support interleaving across
  concurrent `request_id`s later via a `capabilities` flag — out of v1 scope.

### 4.4 Replay response (child → parent), exactly one per request

```json
{"v":1,"type":"replay_response","request_id":"r-000017",
 "output":{"text":"the agent's final response",
   "tool_spans":[{"name":"search_kb","kind":"tool","tool_call_id":null,
                  "input":"rendered judge-facing form or null",
                  "output":"rendered form or null",
                  "args":{"query":"refund policy"},
                  "attributes":{}}],
   "metadata":{}}}
```

`output` mirrors `ReplayOutput` exactly (`text` required; `tool_spans[]` as
`ToolSpan` objects — `name`, `kind`, `tool_call_id`, `input`, `output`,
`args`, `attributes`; `metadata` free-form). The parent validates the frame
**through the same Pydantic models** as the Python lane, so Cardinal-#5
attribute enforcement and `Sensitive` wrapping apply identically — the exec
lane gets no laxer schema than the in-process lane.

Or, on failure:

```json
{"v":1,"type":"replay_error","request_id":"r-000017",
 "code":"runner_exception","message":"upstream model 500","retryable":false,"details":{}}
```

`code` SHOULD be a registry code where one fits; unknown codes are recorded
as `runner_exception` with `details.child_code` preserved.

### 4.5 Shutdown

`{"v":1,"type":"shutdown"}` → child flushes, exits 0. Exit code ≠ 0 after a
clean shutdown is logged, not failed.

## 5. Timeouts

The existing `timeouts.replay_seconds` budget applies **per replay_request,
wall-clock, inclusive of tool callbacks** (callback time is the parent's own
lookup, microseconds in practice). Expiry ⇒ existing `runner_timeout`
failure carrying `timeout_seconds`, the in-flight request is abandoned, and —
because a stuck child may be wedged — the parent restarts the child for the
next trace and increments `runtime`'s restart counter (§7). Handshake
timeout (10s) and shutdown grace are fixed protocol constants in v1.

## 6. Failure mapping (uses the shipped registry)

| Event | `failures[].code` | stage/scope | retryable |
|---|---|---|---|
| per-replay deadline exceeded | `runner_timeout` | replay/trace | true |
| child `replay_error` (incl. its `tool_cache_miss`) | as declared / `runner_exception` | replay/trace | per registry |
| malformed frame, unknown child `type`, duplicate `replay_response`, child died mid-request | **`runner_protocol_error`** *(proposed new registry entry: stage replay, scope trace, retryable false; `details`: `raw_excerpt` ≤ 256 chars, `violation`)* | replay/trace | false |
| invalid `hello` / spawn failure | setup failure → CLI exit 2 (existing `InvalidRunnerTarget`-class path) | run | — |

The single new code keeps protocol pathologies distinguishable from agent
exceptions in `failures[]` without forking the error model. Adding it
touches `failure_codes.py` + (if it can ever block) a fix-suggestion —
cascade-catalog entry required.

## 7. Report & manifest additions (defensibility)

New optional fields (additive ⇒ allowed within the schema's stability
contract; consumers tolerate unknown keys):

- `runtime.runner_lane: "python" | "exec"`
- `runtime.exec_runner` (exec lane only): `{argv: [...], executable_sha256,
  runner_name, runner_version, protocol: "whatifd-exec/1", restarts: n}`

`argv`, `executable_sha256`, `runner_name/version`, `protocol` are
deterministic (`x-deterministic: true`); `restarts` is not. This is the §2.2
answer to "which runner produced this verdict."

## 8. Conformance & reference assets (acceptance criteria for the unit)

- `examples/exec_agent_node/` — a ~60-line Node reference runner (no deps).
- A parent-side **conformance harness** (`whatifd exec-check <target>`)
  that runs a child through: hello → 2 replays with cache hit/miss → a
  malformed-frame probe → shutdown, and prints pass/fail per behavior.
- Walkthrough fixture #8: `regression_check` end-to-end via an exec runner,
  byte-equal deterministic subset across two runs (extends the existing
  determinism integration test to the exec lane).
- `docs/runner-contract.md` gains a short "exec lane" section linking here;
  loader error text updated to name both schemes.

## 9. Design decisions (settled at promotion, 2026-06-13)

1. **Concurrency — scale by processes, not in-child concurrency.** v1 pins
   exactly one in-flight `replay_request` per child and preserves per-trace
   isolation. Parallelism across traces is achieved by running multiple child
   *processes* (the parent already parallelizes replay), which keeps each
   child's protocol state trivially correct and matches the per-trace
   isolation the replay kernel assumes. A `capabilities`-negotiated in-child
   concurrency is explicitly deferred to a future version with its own spec.
2. **`hello.runner_version` is disclosure-only in v1**, not floor-relevant. A
   child that won't identify itself does not by itself downgrade the verdict;
   the executable sha256 + argv already satisfy the "which runner produced
   this verdict?" audit need (§2.2, §7). Making identity floor-relevant is a
   policy a later version may add, but the v1 floor is unchanged.
3. **POSIX-only in v1.** argv splitting (POSIX shell-word rules) and line
   buffering are specified for POSIX; Windows is a documented non-target for
   v1 (the loader rejects `exec:` with a clear "POSIX-only in this version"
   message when `os.name != "posix"`). A Windows lane, if demanded, is a
   separate increment.

**Settled integration decision (the load-bearing one for implementation):**
the child is spawned **lazily on the first replay and kept alive across the
session**, but the `Runner` protocol is invoked *per trace*. The exec runner
is therefore a **stateful callable** (`ExecRunner` instance) that owns the
child process and is registered for **deterministic teardown** — the CLI fork
wiring closes it in a `finally` (sending `shutdown`, then SIGTERM→SIGKILL on
the grace timer) after the last trace. This is the one place the exec lane
needs more than the stateless `python:` callable; it is recorded in the
cascade-catalog so the kernel/CLI teardown hook is implemented in lockstep
with `ExecRunner`, never bolted on after.
