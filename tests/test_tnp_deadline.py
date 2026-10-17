"""Real subprocess deadlines and cancellation cleanup without predictor dependencies."""

import asyncio
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_developability_execution import Manager, service_class


SPEC = importlib.util.spec_from_file_location(
    "tnp_deadline_under_test", Path(__file__).parents[1] / "metanano/utils/tnp_wrapper.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


@pytest.fixture
def process_tree(tmp_path):
    script = tmp_path / "predictor.py"
    script.write_text(
        "import os, signal, subprocess, sys, time\n"
        "from pathlib import Path\n"
        "directory = Path(sys.argv[1])\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "if '--child' in sys.argv:\n"
        "    end = time.monotonic() + 30\n"
        "    count = 0\n"
        "    while time.monotonic() < end:\n"
        "        (directory / 'heartbeat').write_text(str(count))\n"
        "        count += 1\n"
        "        time.sleep(0.02)\n"
        "else:\n"
        "    subprocess.Popen([sys.executable, __file__, str(directory), '--child'])\n"
        "    (directory / 'parent.pid').write_text(str(os.getpid()))\n"
        "    time.sleep(30)\n"
    )
    yield [sys.executable, str(script), str(tmp_path)], tmp_path
    pid_path = tmp_path / "parent.pid"
    if pid_path.exists():
        try:
            os.killpg(int(pid_path.read_text()), signal.SIGKILL)
        except ProcessLookupError:
            pass


def assert_process_tree_stopped(directory):
    heartbeat = directory / "heartbeat"
    assert heartbeat.exists()
    stopped = heartbeat.read_text()
    time.sleep(0.1)
    assert heartbeat.read_text() == stopped
    with pytest.raises(ChildProcessError):
        os.waitpid(int((directory / "parent.pid").read_text()), os.WNOHANG)


def test_deadline_terminates_and_reaps_process_tree(process_tree):
    command, directory = process_tree
    execution = module.ProfileExecution(0.6)
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        execution.run(command, timeout=30)
    assert time.monotonic() - started < 3
    assert_process_tree_stopped(directory)


def test_retry_attempts_share_one_budget(monkeypatch):
    clock = [0.0]
    observed = []

    def failed_attempt(self, sequence, name, attempt, *, timeout, context, execution):
        observed.append(timeout)
        clock[0] += 4
        return None

    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.TNPWrapper, "_check_tnp_available", lambda self: True)
    monkeypatch.setattr(module.TNPWrapper, "_run_once", failed_attempt)
    execution = module.ProfileExecution(7)
    assert module.TNPWrapper().profile("G" * 60, execution=execution) is None
    assert observed == [7, 3]


def test_cancellation_holds_slot_until_process_cleanup(process_tree):
    command, directory = process_tree

    class Filter:
        def __init__(self, config):
            pass

        def compute_tnp_profile(self, sequence, *, execution):
            execution.run(command, timeout=30)

    async def run():
        service_type = service_class(Filter)
        manager = Manager()
        service = service_type(None, manager)
        request = asyncio.create_task(service.compute_tnp_profile_async("G" * 60))
        try:
            async with asyncio.timeout(3):
                while not (directory / "heartbeat").exists():
                    await asyncio.sleep(0.01)
            request.cancel()
            await asyncio.sleep(0.03)
            assert manager.tnp_semaphore.locked()
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(request, timeout=3)
            assert not manager.tnp_semaphore.locked()
            assert_process_tree_stopped(directory)
        finally:
            if not request.done():
                request.cancel()
                await asyncio.gather(request, return_exceptions=True)

    asyncio.run(run())


def test_queue_wait_uses_the_same_deadline():
    calls = []

    class Filter:
        def __init__(self, config):
            pass

        def compute_tnp_profile(self, sequence, *, execution):
            calls.append(sequence)

    async def run():
        service_type = service_class(Filter)
        manager = Manager()
        manager.task_timeout = 0.05
        await manager.tnp_semaphore.acquire()
        try:
            service = service_type(None, manager)
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(service.compute_tnp_profile_async("G" * 60), timeout=1)
            assert manager.tnp_semaphore.locked()
            assert calls == []
        finally:
            manager.tnp_semaphore.release()

    asyncio.run(run())


def test_service_timeout_stops_process_before_releasing_slot(process_tree):
    command, directory = process_tree

    class Filter:
        def __init__(self, config):
            pass

        def compute_tnp_profile(self, sequence, *, execution):
            execution.run(command, timeout=30)

    async def run():
        manager = Manager()
        manager.task_timeout = 0.6
        service = service_class(Filter)(None, manager)
        started = time.monotonic()
        result = await service.analyze_async("G" * 60)
        assert result["error_kind"] == "timeout"
        assert result["error"] is True
        assert time.monotonic() - started < 3
        assert not manager.tnp_semaphore.locked()
        assert_process_tree_stopped(directory)

    asyncio.run(run())


def test_cancelled_execution_never_launches_a_process(process_tree):
    command, directory = process_tree
    execution = module.ProfileExecution()
    execution.cancel()
    with pytest.raises(TimeoutError):
        execution.run(command, timeout=30)
    assert not (directory / "parent.pid").exists()
