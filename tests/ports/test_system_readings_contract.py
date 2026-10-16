from __future__ import annotations

import unittest

from _core_path import CoreModulePath

CoreModulePath.activate()

from _host_fakes import FakeSystemReadings, FixedSource

from agent_core._adapters.host.macos_readings import MacosReadings
from agent_core._ports.host import Level, SystemReadings

SWAP_IN_USE_BYTES = 2 * 1024 ** 3
CRITICAL_SYSCTL_LEVEL = "4"
SERIOUS_THERMAL_STATE = 2


class SystemReadingsContract:
    def readings(self) -> SystemReadings:
        raise NotImplementedError

    def test_the_memory_pressure_is_read_on_the_one_scale(self) -> None:
        self.assertIsInstance(self.readings().memory_pressure(), Level)

    def test_the_thermal_state_is_read_on_the_one_scale(self) -> None:
        self.assertIsInstance(self.readings().thermal(), Level)

    def test_the_swap_in_use_is_a_whole_number_of_bytes_never_below_zero(self) -> None:
        swap = self.readings().swap_used()
        self.assertIsInstance(swap, int)
        self.assertGreaterEqual(swap, 0)


class RefusedReadingsContract:
    def refused(self) -> SystemReadings:
        raise NotImplementedError

    def test_every_refused_reading_is_none(self) -> None:
        readings = self.refused()
        self.assertEqual((None, None, None), (readings.memory_pressure(), readings.thermal(), readings.swap_used()))


class TestFakeSystemReadingsKeepTheContract(SystemReadingsContract, RefusedReadingsContract, unittest.TestCase):
    def readings(self) -> SystemReadings:
        return FakeSystemReadings(Level.ELEVATED, Level.SERIOUS, SWAP_IN_USE_BYTES)

    def refused(self) -> SystemReadings:
        return FakeSystemReadings(None, None, None)


class TestTheMacosReadingsKeepTheContract(SystemReadingsContract, RefusedReadingsContract, unittest.TestCase):
    def readings(self) -> SystemReadings:
        return MacosReadings(FixedSource(CRITICAL_SYSCTL_LEVEL), FixedSource(SERIOUS_THERMAL_STATE),
                             FixedSource(SWAP_IN_USE_BYTES))

    def refused(self) -> SystemReadings:
        return MacosReadings(FixedSource(None), FixedSource(None), FixedSource(None))


if __name__ == "__main__":
    unittest.main()
