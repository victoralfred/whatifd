"""Determinism over the `exec:` runner lane — fixture #8.

The exec lane (`whatifd-exec/1`) must be byte-deterministic end-to-end:
two fresh runs over the same exec runner + traces produce byte-equal
deterministic subsets, exactly like the `python:` lane. This pins the
property the CI-gating use case depends on (a gate that flaps is useless),
extended to a non-Python runner driven over a subprocess.

The reference child is a fixed-output deterministic agent; combined with
the seeded paired-percentile bootstrap, the deterministic subset of the
report MUST be byte-identical across runs.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from whatifd.adapters.stub import StubScorer, StubTraceSource, StubTraceSpec
from whatifd.cli_pipeline import build_delta_fn
from whatifd.config import ChangeConfig
from whatifd.pipeline import run_pipeline
from whatifd.runner_loader import load_runner
from whatifd.serialization.canonical import canonical_json_bytes
from whatifd.serialization.determinism import extract_deterministic_subset
from whatifd.serialization.encoder import encode_report_v01
from whatifd.types.policy import DecisionPolicy, TrustFloor

from ._fixtures import _default_cache_summary, _default_methodology, _default_runtime

_DETERMINISTIC_CHILD = """\
import sys, json

def send(o):
    sys.stdout.write(json.dumps(o) + "\\n"); sys.stdout.flush()

def recv():
    line = sys.stdin.readline()
    return json.loads(line) if line else None

send({"v":1,"type":"hello","protocol":"whatifd-exec/1",
      "runner_name":"det","runner_version":"1.0"})
recv()  # hello_ack
while True:
    f = recv()
    if f is None or f.get("type") == "shutdown":
        break
    msg = f.get("trace_input", {}).get("user_message", "")
    # Fixed, input-determined output → fully deterministic.
    send({"v":1,"type":"replay_response","request_id":f.get("request_id"),
          "output":{"text":"replayed:" + msg,"tool_spans":[],"metadata":{}}})
"""


def _specs() -> list[StubTraceSpec]:
    failures = [
        StubTraceSpec(
            trace_id=f"f-{i:02d}",
            user_message=f"failure prompt {i}",
            original_response=f"failure response {i}",
            cohort="failure",
        )
        for i in range(8)
    ]
    baselines = [
        StubTraceSpec(
            trace_id=f"b-{i:02d}",
            user_message=f"baseline prompt {i}",
            original_response=f"baseline response {i}",
            cohort="baseline",
        )
        for i in range(8)
    ]
    return [*failures, *baselines]


def _run_exec_and_extract_subset(tmp_path) -> dict[str, Any]:
    from whatifd.exec_runner import ExecRunner

    child = tmp_path / "det_agent.py"
    child.write_text(_DETERMINISTIC_CHILD, encoding="utf-8")
    floor = TrustFloor()
    policy = DecisionPolicy()
    # Resolve through the production loader so the test exercises the real
    # `exec:` dispatch path (and the loader — not the test — sets `kind`).
    loaded = load_runner(f"exec:{sys.executable} {child}")
    runner = loaded.callable_
    assert isinstance(runner, ExecRunner)  # `exec:` resolves to an ExecRunner
    delta_fn = build_delta_fn(
        loaded_runner=loaded,
        scorer=StubScorer(),
        change=ChangeConfig(system_prompt="new prompt", model=None),
        replay_timeout_seconds=10.0,
    )
    try:
        report = run_pipeline(
            StubTraceSource(specs=_specs()),
            delta_fn=delta_fn,
            floor=floor,
            policy=policy,
            runtime=_default_runtime(floor=floor, policy=policy),
            methodology=_default_methodology(),
            cache_summary=_default_cache_summary(),
        )
    finally:
        runner.close()
    return extract_deterministic_subset(json.loads(encode_report_v01(report)))


@pytest.mark.skipif(sys.platform == "win32", reason="exec: lane is POSIX-only in v1")
def test_exec_lane_deterministic_subset_byte_equal(tmp_path) -> None:
    # Two fresh runs (fresh subprocess each) → byte-equal deterministic subset.
    # Compare via the serialization boundary (canonical_json_bytes), matching
    # the python-lane determinism suite, rather than a raw json.dumps.
    subset_a = _run_exec_and_extract_subset(tmp_path)
    subset_b = _run_exec_and_extract_subset(tmp_path)
    assert canonical_json_bytes(subset_a) == canonical_json_bytes(subset_b)
