from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT_DEPTH = 4
LIB_DIR = Path(__file__).resolve().parents[ROOT_DEPTH] / "lib"
LEDGER = Path("ledger")
REGISTRY_URL = "https://registry.invalid/confirm"
REGISTRY_TIMEOUT_SECONDS = 10
HTTP_OK = 200
EXIT_FAILURE = 1


class RegistryError(ConnectionError):
    pass


def main() -> None:
    sys.path.insert(0, str(LIB_DIR))
    from records import RecordError

    args = parser().parse_args()
    try:
        args.handler(args)
    except (RegistryError, RecordError) as error:
        print(error, file=sys.stderr)
        sys.exit(EXIT_FAILURE)


def parser() -> argparse.ArgumentParser:
    program = argparse.ArgumentParser(prog="file_records.py")
    commands = program.add_subparsers(required=True)
    commands.add_parser("list").set_defaults(handler=list_records)
    filing = commands.add_parser("file")
    filing.add_argument("title")
    filing.set_defaults(handler=file_record)
    return program


def list_records(_args: argparse.Namespace) -> None:
    for path in sorted(LEDGER.glob("*.md")):
        print(path.name)


def file_record(args: argparse.Namespace) -> None:
    from records import write_atomically

    confirm(args.title)
    path = LEDGER / record_name(args.title)
    write_atomically(path, args.title + "\n")
    print(path.name)


def record_name(title: str) -> str:
    from records import RecordName

    return RecordName(title).text()


def confirm(title: str) -> None:
    query = urllib.parse.urlencode({"title": title})
    try:
        with urllib.request.urlopen(f"{REGISTRY_URL}?{query}", timeout=REGISTRY_TIMEOUT_SECONDS) as response:
            accepted = response.status == HTTP_OK
    except urllib.error.URLError as error:
        raise RegistryError(f"the registry at {REGISTRY_URL} is offline ({error.reason})") from error
    if not accepted:
        raise RegistryError(f"the registry refused the title {title!r}")


if __name__ == "__main__":
    main()
