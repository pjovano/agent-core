from __future__ import annotations

from collections.abc import Sequence

from agent_core._domain.manifest import DomainManifest

READ_RULE = "Read({path}/**)"


class SettingsBlocks:
    def __init__(self, domain: DomainManifest, neighbours: Sequence[DomainManifest]) -> None:
        self._domain = domain
        self._neighbours = [neighbour for neighbour in neighbours if neighbour.name != domain.name]

    def as_dict(self) -> dict:
        return {"permissions": self._permissions(), "sandbox": self._sandbox()}

    def _permissions(self) -> dict:
        denied = [READ_RULE.format(path=path) for path in self._denied_paths()]
        return NonEmpty({"allow": list(self._domain.policy.allow), "deny": denied}).entries()

    def _sandbox(self) -> dict:
        policy = self._domain.policy
        filesystem = NonEmpty({"allowWrite": self._write_paths(), "denyRead": self._denied_paths()}).entries()
        sandbox = {"enabled": True, "filesystem": filesystem, "network": self._network()}
        return NonEmpty({**sandbox, "excludedCommands": list(policy.excluded_commands)}).entries()

    def _network(self) -> dict:
        policy = self._domain.policy
        network = NonEmpty({"allowedDomains": list(policy.network_hosts)}).entries()
        if policy.allow_local_binding:
            network["allowLocalBinding"] = True
        return network

    def _write_paths(self) -> list[str]:
        folder_paths = [path for folder in self._domain.writable_folders() for path in folder.write_paths()]
        return folder_paths + list(self._domain.policy.write_paths)

    def _denied_paths(self) -> list[str]:
        own = self._domain.folder_names()
        guarded = {folder.path for neighbour in self._neighbours for folder in neighbour.sensitive_folders()
                   if folder.name not in own}
        return sorted(guarded)


class NonEmpty:
    def __init__(self, entries: dict) -> None:
        self._entries = entries

    def entries(self) -> dict:
        return {key: value for key, value in self._entries.items() if value != [] and value != {}}
