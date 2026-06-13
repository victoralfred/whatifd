"""`exec:` runner lane — drive a child process over NDJSON stdio.

Implements the `whatifd-exec/1` protocol specified in
`docs/runner-contract-exec.md`: a language-agnostic runner that runs the
user's replay entry point as a child process speaking line-buffered NDJSON
over stdin/stdout, so non-Python agents satisfy the runner contract without
an SDK.

This module owns the **parent** side. `ExecRunner` is a *stateful* callable
that satisfies the `Runner` protocol (`(trace_input, config, tool_cache) ->
ReplayOutput`) but, unlike the stateless `python:` callable, owns a child
process across the whole session: the child is spawned lazily on the first
call and reused for every subsequent trace. The owner (the CLI fork wiring)
MUST call `close()` (or use the runner as a context manager) so the child is
shut down deterministically — see the cascade-catalog entry "exec: runner
lane".

Doctrine notes carried from the spec:

- **Cache keying stays in core (constraint §2.1).** The child never computes
  cache keys; a `tool_lookup` frame is answered by this parent using the one
  true `ToolCache.lookup`.
- **No laxer schema (constraint §4.4).** The child's `replay_response.output`
  is validated through the *same* `ReplayOutput` Pydantic model as the Python
  lane, so cardinal-#5 `Sensitive[str]` wrapping of tool-span content applies
  identically.
- **POSIX-only in v1 (§9.3).** `select`-based read timeouts and POSIX argv
  rules; the loader rejects `exec:` on non-POSIX platforms before we get here.
"""

from __future__ import annotations

import contextlib
import json
import select
import subprocess
from typing import TYPE_CHECKING, Any

from whatifd.contract import ReplayConfig, ReplayOutput, ToolCache, TraceInput
from whatifd.serialization import canonical_json_bytes

if TYPE_CHECKING:
    from collections.abc import Mapping

PROTOCOL = "whatifd-exec/1"
_HELLO_TIMEOUT_S = 10.0
_SHUTDOWN_GRACE_S = 5.0


class ExecRunnerError(Exception):
    """A protocol- or process-level failure in the exec runner lane.

    Carries an actionable message plus a short `details` mapping (e.g. a
    `raw_excerpt` of the offending frame) so the caller can map it onto the
    failure registry (`runner_protocol_error` once that code lands; until
    then the CLI maps it to `runner_exception` with `details.child_code`).
    Cardinal #1: a structured failure, never a bare stack trace.
    """

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})


class ExecRunner:
    """Stateful `Runner` that drives an `exec:` child over NDJSON stdio.

    Spawn is lazy (first `__call__`); the child is reused across traces and
    torn down by `close()`. Safe to use as a context manager::

        with ExecRunner(["./replay-agent"]) as run:
            out = run(trace_input, replay_config, tool_cache)
    """

    __slots__ = ("_argv", "_proc", "_runner_name", "_runner_version", "_started")

    def __init__(self, argv: list[str]) -> None:
        if not argv:
            raise ExecRunnerError("exec runner argv is empty.")
        self._argv = list(argv)
        self._proc: subprocess.Popen[str] | None = None
        self._runner_name: str | None = None
        self._runner_version: str | None = None
        self._started = False

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Spawn the child and complete the `hello`/`hello_ack` handshake.

        Idempotent: a second call is a no-op. A child whose first line is
        not a valid `hello` within the handshake window fails the run at
        setup (no per-trace retries — a broken binary stays broken).
        """
        if self._started:
            return
        try:
            # argv is the operator-supplied runner target, executed directly
            # (no shell=True, no interpolation) — the same trust model as a
            # `python:` runner reference.
            self._proc = subprocess.Popen(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # line-buffered
            )
        except (OSError, ValueError) as exc:
            raise ExecRunnerError(
                f"exec runner could not spawn {self._argv!r}: {exc}. "
                "Check that the executable exists and is runnable."
            ) from exc

        hello = self._recv(_HELLO_TIMEOUT_S)
        if hello.get("type") != "hello" or hello.get("protocol") != PROTOCOL:
            raise ExecRunnerError(
                f"exec runner handshake failed: expected a {PROTOCOL!r} `hello` frame first.",
                details={"raw_excerpt": _excerpt(hello)},
            )
        self._runner_name = _as_str_or_none(hello.get("runner_name"))
        self._runner_version = _as_str_or_none(hello.get("runner_version"))
        self._send(
            {
                "v": 1,
                "type": "hello_ack",
                "whatifd_version": _whatifd_version(),
                "tool_cache_policy": "use-original",
            }
        )
        self._started = True

    def close(self) -> None:
        """Shut the child down: `shutdown` frame, then SIGTERM→SIGKILL."""
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                with contextlib.suppress(BrokenPipeError, ValueError, OSError):
                    self._send({"v": 1, "type": "shutdown"})
                try:
                    proc.wait(timeout=_SHUTDOWN_GRACE_S)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=_SHUTDOWN_GRACE_S)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
        finally:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    with contextlib.suppress(OSError):
                        stream.close()
            self._proc = None
            self._started = False

    def __enter__(self) -> ExecRunner:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- the Runner protocol ----------------------------------------------

    def __call__(
        self,
        trace_input: TraceInput,
        config: ReplayConfig,
        tool_cache: ToolCache,
    ) -> ReplayOutput:
        """Replay one trace through the child and return its `ReplayOutput`.

        Drives `replay_request → (tool_lookup → tool_result)* →
        replay_response`. Tool lookups are answered with the canonical
        `ToolCache.lookup` (keying stays in core). The response frame is
        validated through `ReplayOutput`, so the exec lane gets no laxer
        schema than the in-process lane.
        """
        if not self._started:
            self.start()

        request_id = "r-0"
        self._send(
            {
                "v": 1,
                "type": "replay_request",
                "request_id": request_id,
                "trace_input": {
                    "user_message": trace_input.user_message,
                    "metadata": dict(trace_input.metadata),
                },
                "replay_config": {
                    "system_prompt": config.system_prompt,
                    "model": config.model,
                    "overrides": dict(config.overrides),
                },
            }
        )

        # Serial callback loop: the child either asks for a tool lookup
        # (answered here, in-core) or returns its final response/error.
        while True:
            frame = self._recv(None)
            ftype = frame.get("type")
            if ftype == "tool_lookup":
                self._answer_tool_lookup(frame, request_id, tool_cache)
                continue
            if ftype == "replay_response":
                return self._build_output(frame)
            if ftype == "replay_error":
                code = _as_str_or_none(frame.get("code")) or "runner_exception"
                message = _as_str_or_none(frame.get("message")) or "exec runner replay_error"
                raise ExecRunnerError(
                    f"exec runner replay_error ({code}): {message}",
                    details={"child_code": code, "child_details": frame.get("details")},
                )
            raise ExecRunnerError(
                f"exec runner sent an unexpected frame type {ftype!r} "
                "during replay (expected tool_lookup | replay_response | replay_error).",
                details={"raw_excerpt": _excerpt(frame)},
            )

    # -- internals ---------------------------------------------------------

    def _answer_tool_lookup(
        self, frame: Mapping[str, Any], request_id: str, tool_cache: ToolCache
    ) -> None:
        tool_name = _as_str_or_none(frame.get("tool_name"))
        args = frame.get("args")
        lookup_id = frame.get("lookup_id")
        if tool_name is None or not isinstance(args, dict):
            raise ExecRunnerError(
                "exec runner sent a malformed tool_lookup (missing tool_name or non-object args).",
                details={"raw_excerpt": _excerpt(frame)},
            )
        cached = tool_cache.lookup(tool_name, args)
        reply: dict[str, Any] = {
            "v": 1,
            "type": "tool_result",
            "request_id": request_id,
            "lookup_id": lookup_id,
            "hit": cached is not None,
        }
        if cached is not None:
            # Cached outputs are JSON values already (the cache is loaded
            # from serialized tool spans). Strings go on `output`; other
            # JSON values go on `output_json` per the spec.
            if isinstance(cached, str):
                reply["output"] = cached
            else:
                reply["output_json"] = cached
        self._send(reply)

    def _build_output(self, frame: Mapping[str, Any]) -> ReplayOutput:
        output = frame.get("output")
        if not isinstance(output, dict):
            raise ExecRunnerError(
                "exec runner replay_response is missing a valid `output` object.",
                details={"raw_excerpt": _excerpt(frame)},
            )
        try:
            # Same Pydantic model as the Python lane → cardinal-#5 wrapping
            # of tool-span content + schema enforcement, identically.
            return ReplayOutput.model_validate(output)
        except Exception as exc:
            raise ExecRunnerError(
                f"exec runner replay_response.output failed validation: {exc}",
                details={"raw_excerpt": _excerpt(output)},
            ) from exc

    def _send(self, frame: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise ExecRunnerError("exec runner child is not running (no stdin).")
        # One JSON object per newline-terminated line. Encoded via the
        # serialization package's canonical helper: this is a process-local
        # control frame (not a report artifact), so it does not traverse the
        # redaction graph walk — the same category as cache-key encoding —
        # and routing through `whatifd.serialization` keeps the cardinal-#5
        # `json.dumps` boundary lint satisfied. Sorted keys are irrelevant
        # to the wire (JSON object order is not significant).
        line = canonical_json_bytes(frame).decode("ascii")
        try:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise ExecRunnerError(
                f"exec runner child closed its input unexpectedly: {exc}.",
                details={"died": True},
            ) from exc

    def _recv(self, timeout: float | None) -> dict[str, Any]:
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise ExecRunnerError("exec runner child is not running (no stdout).")
        if timeout is not None:
            ready, _, _ = select.select([proc.stdout], [], [], timeout)
            if not ready:
                raise ExecRunnerError(
                    f"exec runner timed out after {timeout:.1f}s waiting for a frame.",
                    details={"timeout_seconds": timeout},
                )
        line = proc.stdout.readline()
        if line == "":
            code = proc.poll()
            raise ExecRunnerError(
                "exec runner child closed its output (EOF) "
                f"before sending the expected frame (exit code {code}).",
                details={"died": True, "exit_code": code},
            )
        try:
            frame = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExecRunnerError(
                f"exec runner sent a non-JSON line: {exc}.",
                details={"raw_excerpt": line[:256]},
            ) from exc
        if not isinstance(frame, dict):
            raise ExecRunnerError(
                "exec runner sent a JSON value that is not an object.",
                details={"raw_excerpt": line[:256]},
            )
        return frame


def _excerpt(frame: object) -> str:
    try:
        return canonical_json_bytes(frame).decode("ascii")[:256]
    except Exception:
        return repr(frame)[:256]


def _as_str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _whatifd_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("whatifd")
    except PackageNotFoundError:  # pragma: no cover - source checkout without dist metadata
        return "0+unknown"


__all__ = ["PROTOCOL", "ExecRunner", "ExecRunnerError"]
