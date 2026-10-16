from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Protocol

from agent_core._ports.host import Level

PRESSURE_COMMAND = ["sysctl", "-n", "kern.memorystatus_vm_pressure_level"]
PRESSURE_TIMEOUT_SECONDS = 5
PRESSURE_LEVELS = {"1": Level.NORMAL, "2": Level.ELEVATED, "4": Level.CRITICAL}
THERMAL_LEVELS = (Level.NORMAL, Level.ELEVATED, Level.SERIOUS, Level.CRITICAL)

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def run_sysctl(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(arguments, capture_output=True, text=True, timeout=PRESSURE_TIMEOUT_SECONDS)


class PressureSource(Protocol):
    def raw(self) -> str | None: ...


class ThermalSource(Protocol):
    def raw(self) -> int | None: ...


class SwapSource(Protocol):
    def used_bytes(self) -> int | None: ...


class SysctlPressure:
    def __init__(self, run: Runner = run_sysctl) -> None:
        self._run = run

    def raw(self) -> str | None:
        try:
            completed = self._run(PRESSURE_COMMAND)
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip() if completed.returncode == 0 else None


class FoundationThermal:
    def raw(self) -> int | None:
        try:
            from Foundation import NSProcessInfo
        except ImportError:
            return None
        return int(NSProcessInfo.processInfo().thermalState())


class PsutilSwap:
    def used_bytes(self) -> int | None:
        try:
            import psutil
        except ImportError:
            return None
        try:
            return int(psutil.swap_memory().used)
        except OSError:
            return None


class MacosReadings:
    def __init__(self, pressure: PressureSource | None = None, thermal: ThermalSource | None = None,
                 swap: SwapSource | None = None) -> None:
        self._pressure = pressure or SysctlPressure()
        self._thermal = thermal or FoundationThermal()
        self._swap = swap or PsutilSwap()

    def memory_pressure(self) -> Level | None:
        return PRESSURE_LEVELS.get(self._pressure.raw())

    def thermal(self) -> Level | None:
        state = self._thermal.raw()
        return THERMAL_LEVELS[state] if state in range(len(THERMAL_LEVELS)) else None

    def swap_used(self) -> int | None:
        return self._swap.used_bytes()
