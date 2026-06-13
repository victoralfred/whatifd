"""Tests for the `exec:` runner lane (`whatifd-exec/1`).

Drives a real child process (a tiny in-repo Python reference runner) through
the protocol: hello handshake → replay_request → (tool_lookup → tool_result)
→ replay_response → shutdown, plus the error and protocol-violation paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from whatifd.contract import ReplayConfig, ToolCache, TraceInput
from whatifd.exec_runner import ExecRunner, ExecRunnerError
from whatifd.runner_loader import RunnerLoadError, load_runner

# A parametric reference child: it interprets `trace_input.user_message` as a
# command so one script exercises every path.
_REFERENCE_CHILD = """\
import sys, json

def send(o):
    sys.stdout.write(json.dumps(o) + "\\n"); sys.stdout.flush()

def recv():
    line = sys.stdin.readline()
    return json.loads(line) if line else None

send({"v":1,"type":"hello","protocol":"whatifd-exec/1",
      "runner_name":"ref-agent","runner_version":"1.2.3","capabilities":[]})
recv()  # hello_ack

while True:
    f = recv()
    if f is None or f.get("type") == "shutdown":
        break
    rid = f.get("request_id")
    msg = f.get("trace_input", {}).get("user_message", "")
    if msg == "tool":
        send({"v":1,"type":"tool_lookup","request_id":rid,"lookup_id":"L1",
              "tool_name":"search","args":{"q":"refund"}})
        tr = recv()
        send({"v":1,"type":"replay_response","request_id":rid,
              "output":{"text":"hit=" + str(tr.get("hit")) + " out=" + str(tr.get("output")),
                        "tool_spans":[],"metadata":{}}})
    elif msg == "boom":
        send({"v":1,"type":"replay_error","request_id":rid,"code":"runner_exception",
              "message":"upstream 500","retryable":False,"details":{}})
    elif msg == "badtype":
        send({"v":1,"type":"surprise","request_id":rid})
    else:
        send({"v":1,"type":"replay_response","request_id":rid,
              "output":{"text":"replayed:" + msg,"tool_spans":[],"metadata":{}}})
"""

_BAD_HELLO_CHILD = """\
import sys, json
sys.stdout.write(json.dumps({"v":1,"type":"not_hello"}) + "\\n"); sys.stdout.flush()
sys.stdin.readline()
"""

_DIES_CHILD = "import sys; sys.exit(3)\n"


def _child(tmp_path: Path, src: str) -> list[str]:
    script = tmp_path / "child.py"
    script.write_text(src, encoding="utf-8")
    return [sys.executable, str(script)]


def _cfg() -> ReplayConfig:
    return ReplayConfig(system_prompt=None, model=None, overrides={})


def _trace(msg: str) -> TraceInput:
    return TraceInput(user_message=msg, metadata={})


@pytest.mark.skipif(sys.platform == "win32", reason="exec: lane is POSIX-only in v1")
class TestExecRunner:
    def test_happy_path_replay(self, tmp_path: Path) -> None:
        with ExecRunner(_child(tmp_path, _REFERENCE_CHILD)) as run:
            out = run(_trace("hello world"), _cfg(), ToolCache())
        assert out.text == "replayed:hello world"
        assert out.tool_spans == []

    def test_handshake_records_runner_identity(self, tmp_path: Path) -> None:
        run = ExecRunner(_child(tmp_path, _REFERENCE_CHILD))
        try:
            run.start()
            assert run._runner_name == "ref-agent"
            assert run._runner_version == "1.2.3"
        finally:
            run.close()

    def test_child_reused_across_traces(self, tmp_path: Path) -> None:
        with ExecRunner(_child(tmp_path, _REFERENCE_CHILD)) as run:
            first = run(_trace("a"), _cfg(), ToolCache())
            second = run(_trace("b"), _cfg(), ToolCache())
        assert first.text == "replayed:a"
        assert second.text == "replayed:b"

    def test_tool_lookup_hit_answered_in_core(self, tmp_path: Path) -> None:
        # Seed the cache so the canonical lookup for ("search", {"q":"refund"})
        # is a hit — keying stays in core, the child never computes it.
        key = ToolCache._key("search", {"q": "refund"})
        tc = ToolCache(cache={key: "cached tool output"})
        with ExecRunner(_child(tmp_path, _REFERENCE_CHILD)) as run:
            out = run(_trace("tool"), _cfg(), tc)
        assert "hit=True" in out.text
        assert "cached tool output" in out.text

    def test_tool_lookup_miss(self, tmp_path: Path) -> None:
        with ExecRunner(_child(tmp_path, _REFERENCE_CHILD)) as run:
            out = run(_trace("tool"), _cfg(), ToolCache())
        assert "hit=False" in out.text

    def test_replay_error_raises(self, tmp_path: Path) -> None:
        with (
            ExecRunner(_child(tmp_path, _REFERENCE_CHILD)) as run,
            pytest.raises(ExecRunnerError, match="runner_exception"),
        ):
            run(_trace("boom"), _cfg(), ToolCache())

    def test_unexpected_frame_type_raises(self, tmp_path: Path) -> None:
        with (
            ExecRunner(_child(tmp_path, _REFERENCE_CHILD)) as run,
            pytest.raises(ExecRunnerError, match="unexpected frame type"),
        ):
            run(_trace("badtype"), _cfg(), ToolCache())

    def test_bad_handshake_raises(self, tmp_path: Path) -> None:
        run = ExecRunner(_child(tmp_path, _BAD_HELLO_CHILD))
        with pytest.raises(ExecRunnerError, match="handshake failed"):
            run.start()
        run.close()

    def test_child_dies_before_hello(self, tmp_path: Path) -> None:
        run = ExecRunner(_child(tmp_path, _DIES_CHILD))
        with pytest.raises(ExecRunnerError, match=r"EOF|closed its output"):
            run.start()
        run.close()

    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        run = ExecRunner(_child(tmp_path, _REFERENCE_CHILD))
        run.start()
        run.close()
        run.close()  # no raise

    def test_empty_argv_rejected(self) -> None:
        with pytest.raises(ExecRunnerError, match="argv is empty"):
            ExecRunner([])


@pytest.mark.skipif(sys.platform == "win32", reason="exec: lane is POSIX-only in v1")
class TestExecScheme:
    def test_loader_returns_exec_runner(self, tmp_path: Path) -> None:
        loaded = load_runner("exec:./replay-agent --mode whatifd")
        assert loaded.kind == "sync"
        assert isinstance(loaded.callable_, ExecRunner)
        assert loaded.reference == "exec:./replay-agent --mode whatifd"

    def test_loader_argv_split_posix(self) -> None:
        loaded = load_runner('exec:./agent "arg with spaces" -x')
        assert isinstance(loaded.callable_, ExecRunner)
        assert loaded.callable_._argv == ["./agent", "arg with spaces", "-x"]

    def test_loader_empty_exec_command_rejected(self) -> None:
        with pytest.raises(RunnerLoadError, match="missing its command"):
            load_runner("exec:   ")

    def test_loader_unbalanced_quotes_rejected(self) -> None:
        with pytest.raises(RunnerLoadError, match="could not parse"):
            load_runner('exec:./agent "unterminated')
