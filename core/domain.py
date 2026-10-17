from __future__ import annotations

import sys
from pathlib import Path

CORE_LIB = Path(__file__).resolve().parent / "lib"


def main() -> None:
    sys.path.insert(0, str(CORE_LIB))
    from agent_core._domain.cli import CommandLine

    CommandLine().run(sys.argv[1:])


if __name__ == "__main__":
    main()
