"""Pin that `examples/minimal_agent/replay.py` satisfies the `Runner`
contract AND is loadable via the documented `python:<module>:<attr>` form.

The example is a copy-paste starting point for users; if it stops satisfying
the protocol (signature drift, wrong return type) or stops importing via the
documented reference, users inherit the breakage. This test fails first.

The example is a real importable package (`examples/minimal_agent/` with
`__init__.py`), so `load_runner` resolves it the same way a developer's own
`python:my_agent.replay:run` resolves — exercising the cwd-on-path fix in
`whatifd._dynamic_import`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whatifd.contract import ReplayConfig, ReplayOutput, Runner, ToolCache, TraceInput
from whatifd.runner_loader import load_runner

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def loaded_run(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    # Load via the DOCUMENTED reference, from the repo root (as a user runs
    # `whatifd fork` from their project root). This goes through the real
    # loader + the cwd-on-path resolution, not a direct file load.
    monkeypatch.chdir(_REPO_ROOT)
    return load_runner("python:examples.minimal_agent.replay:run").callable_


def test_documented_reference_loads(loaded_run) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(loaded_run, Runner)


def test_run_returns_replay_output(loaded_run) -> None:  # type: ignore[no-untyped-def]
    out = loaded_run(
        TraceInput(user_message="hello"),
        ReplayConfig(system_prompt="You are concise."),
        ToolCache(),
    )
    assert isinstance(out, ReplayOutput)
    assert out.text
    assert out.metadata["runner"] == "examples.minimal_agent"


def test_loader_resolves_user_module_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The core 'customized projects' fix: a runner module in the developer's
    OWN project root resolves via `python:<module>:<attr>` because the loader
    puts the cwd on sys.path (an installed console script otherwise wouldn't).

    Uses a UNIQUE module name and restores sys.path / sys.modules so loading a
    cwd-local module here can't leak into other tests (the loader's
    cwd-on-path is a deliberate, process-lasting side effect)."""
    import sys

    pkg = "_whatifd_cwd_probe_agent"
    (tmp_path / pkg).mkdir()
    (tmp_path / pkg / "__init__.py").write_text("")
    (tmp_path / pkg / "replay.py").write_text(
        "from whatifd.contract import ReplayOutput\n"
        "def run(trace_input, config, tool_cache):\n"
        "    return ReplayOutput(text='from-my-project')\n"
    )
    monkeypatch.chdir(tmp_path)
    saved_path = list(sys.path)
    try:
        loaded = load_runner(f"python:{pkg}.replay:run")
        out = loaded.callable_(
            TraceInput(user_message="x"), ReplayConfig(system_prompt="p"), ToolCache()
        )
        assert out.text == "from-my-project"
    finally:
        sys.path[:] = saved_path
        for mod in [m for m in sys.modules if m == pkg or m.startswith(pkg + ".")]:
            del sys.modules[mod]
