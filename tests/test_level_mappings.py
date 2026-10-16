from __future__ import annotations

import subprocess
import sys
import unittest
from unittest import mock

from _core_path import CoreModulePath

CoreModulePath.activate()

from _host_fakes import FixedSource

from agent_core._adapters.host.macos_readings import FoundationThermal, MacosReadings, PsutilSwap, SysctlPressure
from agent_core._ports.host import Level

ABSENT_MODULE = None


def sysctl_answering(returncode: int, stdout: str):
    return lambda command: subprocess.CompletedProcess(command, returncode, stdout, "")


def sysctl_failing(error: Exception):
    def run(command: list[str]) -> subprocess.CompletedProcess:
        raise error
    return run


def pressure(source) -> Level | None:
    return MacosReadings(pressure=source, thermal=FixedSource(None), swap=FixedSource(None)).memory_pressure()


def thermal(state: int | None) -> Level | None:
    return MacosReadings(pressure=FixedSource(None), thermal=FixedSource(state), swap=FixedSource(None)).thermal()


class TestTheMemoryPressureMapping(unittest.TestCase):
    def test_each_sysctl_level_maps_onto_the_one_scale(self) -> None:
        mapped = {raw: pressure(SysctlPressure(sysctl_answering(0, f"{raw}\n"))) for raw in ("1", "2", "4")}
        self.assertEqual({"1": Level.NORMAL, "2": Level.ELEVATED, "4": Level.CRITICAL}, mapped)

    def test_an_unknown_sysctl_level_is_unread(self) -> None:
        self.assertIsNone(pressure(SysctlPressure(sysctl_answering(0, "3\n"))))

    def test_a_refused_sysctl_is_unread(self) -> None:
        self.assertIsNone(pressure(SysctlPressure(sysctl_answering(1, "4\n"))))

    def test_a_sysctl_that_cannot_run_is_unread(self) -> None:
        self.assertIsNone(pressure(SysctlPressure(sysctl_failing(OSError("no sysctl")))))

    def test_a_sysctl_that_times_out_is_unread(self) -> None:
        self.assertIsNone(pressure(SysctlPressure(sysctl_failing(subprocess.TimeoutExpired("sysctl", 5)))))


class TestTheThermalMapping(unittest.TestCase):
    def test_each_thermal_state_maps_onto_the_one_scale(self) -> None:
        self.assertEqual([Level.NORMAL, Level.ELEVATED, Level.SERIOUS, Level.CRITICAL],
                         [thermal(state) for state in range(4)])

    def test_a_state_beyond_the_scale_is_unread(self) -> None:
        self.assertIsNone(thermal(4))

    def test_a_machine_without_foundation_reads_no_thermal_state(self) -> None:
        with mock.patch.dict(sys.modules, {"Foundation": ABSENT_MODULE}):
            self.assertIsNone(FoundationThermal().raw())


class TestTheSwapReading(unittest.TestCase):
    def test_a_machine_without_psutil_reads_no_swap(self) -> None:
        with mock.patch.dict(sys.modules, {"psutil": ABSENT_MODULE}):
            self.assertIsNone(PsutilSwap().used_bytes())

    def test_swap_is_read_in_whole_bytes(self) -> None:
        fake_psutil = mock.Mock(**{"swap_memory.return_value.used": 1536.0})
        with mock.patch.dict(sys.modules, {"psutil": fake_psutil}):
            self.assertEqual(1536, PsutilSwap().used_bytes())


if __name__ == "__main__":
    unittest.main()
