"""Custom ansible-lint rule: no per-host os_* keys in inventory files.

Repo standard (see CLAUDE.md "Inventory Structure"): a host entry must not
declare `os_family`, `os_distribution`, `os_version` or `os_edition`. For any
host that can run the `setup` module these are hand-maintained duplicates of
gathered facts — they drift silently and nothing reads them. Code that branches
on OS reads `ansible_facts['os_family']`; provisioning code that runs before the
guest exists (roles/cloud_init) branches on inventory GROUP membership instead.

Scope is deliberately narrow: only keys set directly on a host entry underneath
a `hosts:` mapping in an inventory file (kind == "inventory"). It does NOT flag
the same names nested inside a structured var, because those are a different
namespace and legitimate — e.g. `hyperv_guest_config.base_images.<name>.
os_version`, which drives AVMA product-key resolution. Nor does it look at
group_vars/host_vars files (kind == "vars"); no host_vars file sets these today,
and widening it there is a separate call.

Escape hatch for a genuinely fact-less device (a network switch, a UPS card):
put the OS in a comment, or `# noqa: no-host-os-vars` if it must be a var.

Not autofix-capable: deleting a var is not a safe mechanical transform, since a
host that truly cannot gather facts may have nothing else recording its OS.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from ansiblelint.errors import MatchError
from ansiblelint.rules import AnsibleLintRule
from ansiblelint.skip_utils import get_rule_skips_from_line

if TYPE_CHECKING:
    from ansiblelint.file_utils import Lintable

# The per-host OS metadata keys this rule forbids.
BANNED_KEYS: frozenset[str] = frozenset(
    {"os_family", "os_distribution", "os_version", "os_edition"},
)


def find_host_os_vars(data: Any) -> list[tuple[str, str, int]]:
    """Return (hostname, key, line) for every banned key on a host entry.

    Walks an inventory tree looking for `hosts:` mappings at any depth (they
    appear under `all:` and under every group in `children:`). `line` is 1-based
    and comes from ruamel round-trip position data when available, else 0.
    """
    found: list[tuple[str, str, int]] = []

    def line_of(node: Any, key: str) -> int:
        lc = getattr(node, "lc", None)
        if lc is None or not hasattr(lc, "data"):
            return 0
        pos = lc.data.get(key)
        return pos[0] + 1 if pos else 0

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key == "hosts" and isinstance(value, dict):
                for hostname, host_vars in value.items():
                    # `hosts:` entries are commonly null (`hostname:` alone).
                    if not isinstance(host_vars, dict):
                        continue
                    for banned in BANNED_KEYS.intersection(host_vars):
                        found.append(
                            (str(hostname), banned, line_of(host_vars, banned)),
                        )
                continue
            walk(value)

    walk(data)
    return found


class NoHostOsVarsRule(AnsibleLintRule):
    """Host entries must not declare os_* metadata."""

    id = "no-host-os-vars"
    severity = "MEDIUM"
    tags = ["idiom"]
    version_changed = "1.0.0"
    _ids = {
        "no-host-os-vars[inventory]": "os_* metadata belongs in gathered facts",
    }

    def matchyaml(self, file: Lintable) -> list[MatchError]:
        if str(file.kind) != "inventory":
            return []
        try:
            from ruamel.yaml import YAML

            data = YAML(typ="rt").load(file.content)
        except Exception:  # pragma: no cover - unparseable YAML is another rule's job
            return []

        # ansible-lint applies `# noqa` automatically to task- and play-level
        # matches, but not to a rule that walks an inventory tree itself, so
        # honor the comment explicitly against the offending line.
        lines = file.content.splitlines()

        def skipped(lineno: int) -> bool:
            if not 0 < lineno <= len(lines):
                return False
            skips = get_rule_skips_from_line(lines[lineno - 1], file, lineno)
            return bool({self.id, "no-host-os-vars[inventory]"}.intersection(skips))

        return [
            self.create_matcherror(
                f"Host '{host}' sets '{key}'. Per-host OS metadata duplicates "
                "gathered facts — read ansible_facts['os_family'] instead, or "
                "branch on inventory group membership when the host does not "
                "exist yet at render time.",
                filename=file,
                lineno=line,
                tag="no-host-os-vars[inventory]",
            )
            for host, key, line in find_host_os_vars(data)
            if not skipped(line)
        ]


# Loaded only under pytest — smoke test the tree walk.
if "pytest" in sys.modules:  # pragma: no cover
    import pytest
    from ruamel.yaml import YAML

    def _load(text: str) -> Any:
        return YAML(typ="rt").load(text)

    def test_flags_host_entry_key() -> None:
        data = _load(
            "all:\n"
            "  hosts:\n"
            "    web-1:\n"
            "      ansible_host: 10.0.0.1\n"
            "      os_family: RedHat\n",
        )
        assert find_host_os_vars(data) == [("web-1", "os_family", 5)]

    def test_flags_hosts_nested_under_children() -> None:
        data = _load(
            "all:\n"
            "  children:\n"
            "    rocky:\n"
            "      hosts:\n"
            "        db-1:\n"
            "          os_distribution: Rocky\n",
        )
        assert find_host_os_vars(data) == [("db-1", "os_distribution", 6)]

    def test_ignores_nested_structured_vars() -> None:
        # hyperv_guest_config.base_images.<name>.os_version is a different
        # namespace and must not be flagged.
        data = _load(
            "all:\n"
            "  hosts:\n"
            "    hv-1:\n"
            "      hyperv_guest_config:\n"
            "        base_images:\n"
            "          server2025:\n"
            "            os_version: '2025'\n",
        )
        assert find_host_os_vars(data) == []

    def test_ignores_group_vars_block() -> None:
        # Only `hosts:` entries are in scope, not a group's `vars:` block.
        data = _load(
            "all:\n"
            "  vars:\n"
            "    os_family: RedHat\n"
            "  hosts:\n"
            "    web-1:\n",
        )
        assert find_host_os_vars(data) == []

    def test_tolerates_bare_host_entries() -> None:
        data = _load("all:\n  hosts:\n    web-1:\n    web-2:\n")
        assert find_host_os_vars(data) == []

    @pytest.mark.parametrize("key", sorted(BANNED_KEYS))
    def test_every_banned_key_is_caught(key: str) -> None:
        data = _load(f"all:\n  hosts:\n    h:\n      {key}: x\n")
        assert [f for _, f, _ in find_host_os_vars(data)] == [key]
