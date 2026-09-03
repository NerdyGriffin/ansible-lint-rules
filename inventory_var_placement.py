"""Custom ansible-lint rule: built-in vars in the inventory file, others out.

Convention: how a host is reached should be answerable by reading ONE file.
Ansible's built-in behavioral/connection vars (`ansible_user`,
`ansible_connection`, `ansible_become*`, `ansible_host`, ...) are therefore
declared in the inventory file that declares the host — on the host entry or on
a group's `vars:` block — and not scattered across `group_vars/<g>/main.yml` and
`host_vars/<h>/main.yml`.

The reason is precedence. Resolution runs by group depth and then alphabetically
among groups of equal depth, which no reader computes reliably in their head;
and it runs counter-intuitively here, since `group_vars/*` OUTRANKS a `vars:`
block in the inventory file. Connection vars are also the ones whose precedence
bites hardest — an `ansible_become` VARIABLE outranks a task's `become:` KEYWORD,
so a task that explicitly asks not to escalate still runs as root.

TWO DIRECTIONS, ONE LIST
------------------------
Both subtags are decided by membership in `BUILTIN_VARS`:

* `[builtin-outside-inventory]` — a built-in defined in `group_vars/` or
  `host_vars/`. Move it to the inventory file.
* `[non-builtin-in-inventory]` — a non-built-in defined on a host entry or a
  group `vars:` block in the inventory file. Move it to `group_vars`/`host_vars`,
  which keeps the inventory file about reachability.

The second direction is what stops the inventory file becoming a dumping ground
once the first direction pushes traffic toward it.

Note that `BUILTIN_VARS` deliberately includes names with no `ansible_` prefix —
`become`, `proxmox_api_host`, `wsl_user` are real connection-plugin vars. A
prefix test would exile them from the inventory file, which is exactly where
they belong.

Not autofix-capable: moving a variable between files is not a transform
ansible-lint can perform, and doing it by hand demands a before/after resolution
diff anyway, because `group_vars/*` and the inventory file sit at different
precedence ranks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ansiblelint.errors import MatchError
from ansiblelint.rules import AnsibleLintRule
from ansiblelint.skip_utils import get_rule_skips_from_line

try:  # pragma: no cover - import shape differs between rulesdir and package use
    from ansible_builtin_vars import BUILTIN_VARS
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).parent))
    from ansible_builtin_vars import BUILTIN_VARS

if TYPE_CHECKING:
    from ansiblelint.file_utils import Lintable

OUTSIDE_TAG = "inventory-var-placement[builtin-outside-inventory]"
INSIDE_TAG = "inventory-var-placement[non-builtin-in-inventory]"

# Reserved group-node keys. These structure the inventory; they are not vars.
GROUP_KEYS: frozenset[str] = frozenset({"hosts", "children", "vars"})


def line_of(node: Any, key: Any) -> int:
    """Return the 1-based line for `key` in a ruamel round-trip node."""
    lc = getattr(node, "lc", None)
    if lc is None or not hasattr(lc, "data"):
        return 0
    pos = lc.data.get(key)
    return pos[0] + 1 if pos else 0


def find_non_builtins_in_inventory(data: Any) -> list[tuple[str, str, int]]:
    """Return (where, varname, line) for non-built-ins set in an inventory file.

    Walks the group structure strictly — `hosts:`, `children:` and `vars:` only.
    Group NAMES are never treated as variables: a group called
    `ansible_control_nodes` is a group, not a var, and an earlier draft of this
    rule reported exactly that as a finding.
    """
    found: list[tuple[str, str, int]] = []

    def check_mapping(where: str, mapping: Any) -> None:
        if not isinstance(mapping, dict):
            return
        for key, value in mapping.items():
            name = str(key)
            if name in BUILTIN_VARS:
                continue
            # A structured value is inventory data (vm_spec, network, ...) that
            # a role consumes wholesale; the convention is about scalar
            # connection settings, so leave composites alone.
            if isinstance(value, (dict, list)):
                continue
            found.append((where, name, line_of(mapping, key)))

    def walk_group(name: str, group: Any) -> None:
        if not isinstance(group, dict):
            return
        check_mapping(f"group '{name}'", group.get("vars"))

        hosts = group.get("hosts")
        if isinstance(hosts, dict):
            for hostname, host_vars in hosts.items():
                check_mapping(f"host '{hostname}'", host_vars)

        children = group.get("children")
        if isinstance(children, dict):
            for child_name, child in children.items():
                walk_group(str(child_name), child)

    if isinstance(data, dict):
        for group_name, group in data.items():
            walk_group(str(group_name), group)
    return found


def find_builtins_in_vars_file(data: Any) -> list[tuple[str, int]]:
    """Return (varname, line) for built-ins defined in a group/host vars file.

    Top-level keys only — a nested `ansible_user` is a field inside somebody
    else's structure, not a variable Ansible resolves under that name.
    """
    if not isinstance(data, dict):
        return []
    return [
        (str(key), line_of(data, key)) for key in data if str(key) in BUILTIN_VARS
    ]


def inventory_vars_dir(path: Path) -> str | None:
    """Return 'group_vars'/'host_vars' if `path` is an INVENTORY vars file.

    Role `vars/` and playbook vars files share ansible-lint's `vars` kind, so the
    directory name is what distinguishes them; without this check the rule would
    order a role's own `vars/main.yml` into an inventory file.
    """
    for parent in path.parents:
        if parent.name in {"group_vars", "host_vars"}:
            return parent.name
    return None


class InventoryVarPlacementRule(AnsibleLintRule):
    """Built-in vars belong in the inventory file; other vars do not."""

    id = "inventory-var-placement"
    severity = "MEDIUM"
    tags = ["idiom"]
    version_changed = "1.1.0"
    _ids = {
        OUTSIDE_TAG: "built-in var defined outside the inventory file",
        INSIDE_TAG: "non-built-in var defined in the inventory file",
    }

    def matchyaml(self, file: Lintable) -> list[MatchError]:
        kind = str(file.kind)
        if kind not in {"inventory", "vars"}:
            return []

        path = Path(str(file.path))
        vars_dir = inventory_vars_dir(path)
        if kind == "vars" and vars_dir is None:
            return []

        from ruamel.yaml import YAML
        from ruamel.yaml.error import YAMLError

        try:
            data = YAML(typ="rt").load(file.content)
        except YAMLError:  # pragma: no cover - malformed YAML is load-failure's job
            return []

        lines = file.content.splitlines()

        def skipped(lineno: int, tag: str) -> bool:
            if not 0 < lineno <= len(lines):
                return False
            skips = get_rule_skips_from_line(lines[lineno - 1], file, lineno)
            return bool({self.id, tag}.intersection(skips))

        if kind == "vars":
            return [
                self.create_matcherror(
                    f"'{name}' is one of Ansible's built-in connection variables, "
                    f"so it belongs on the host entry or group vars: block in the "
                    f"inventory file, not in {vars_dir}/. Keeping them in one file "
                    "is what makes a host's connection settings readable without "
                    "resolving group precedence.",
                    filename=file,
                    lineno=line,
                    tag=OUTSIDE_TAG,
                )
                for name, line in find_builtins_in_vars_file(data)
                if not skipped(line, OUTSIDE_TAG)
            ]

        return [
            self.create_matcherror(
                f"{where} sets '{name}', which is not one of Ansible's built-in "
                "connection variables. Move it to group_vars/ or host_vars/ so "
                "the inventory file stays about how hosts are reached.",
                filename=file,
                lineno=line,
                tag=INSIDE_TAG,
            )
            for where, name, line in find_non_builtins_in_inventory(data)
            if not skipped(line, INSIDE_TAG)
        ]


if "pytest" in sys.modules:  # pragma: no cover
    from ruamel.yaml import YAML

    def _load(text: str) -> Any:
        return YAML(typ="rt").load(text)

    # --- direction 1: built-ins in a vars file -----------------------------

    def test_flags_builtin_in_vars_file() -> None:
        data = _load("---\nansible_user: root\nmy_setting: 1\n")
        assert find_builtins_in_vars_file(data) == [("ansible_user", 2)]

    def test_flags_unprefixed_builtin_in_vars_file() -> None:
        # `become` is a real connection var despite carrying no prefix.
        assert find_builtins_in_vars_file(_load("---\nbecome: true\n")) == [
            ("become", 2),
        ]

    def test_ignores_nested_builtin_in_vars_file() -> None:
        data = _load("---\nsome_config:\n  ansible_user: root\n")
        assert find_builtins_in_vars_file(data) == []

    # --- direction 2: non-built-ins in the inventory file -------------------

    def test_flags_non_builtin_on_host_entry() -> None:
        data = _load("all:\n  hosts:\n    web-1:\n      my_role_flag: true\n")
        assert find_non_builtins_in_inventory(data) == [
            ("host 'web-1'", "my_role_flag", 4),
        ]

    def test_allows_builtin_on_host_entry() -> None:
        data = _load("all:\n  hosts:\n    web-1:\n      ansible_host: 10.0.0.1\n")
        assert find_non_builtins_in_inventory(data) == []

    def test_flags_non_builtin_in_group_vars_block() -> None:
        data = _load("all:\n  vars:\n    my_flag: 1\n  hosts:\n    web-1:\n")
        assert find_non_builtins_in_inventory(data) == [("group 'all'", "my_flag", 3)]

    def test_group_names_are_not_variables() -> None:
        # Regression: a group named ansible_control_nodes is a GROUP.
        data = _load(
            "all:\n"
            "  children:\n"
            "    ansible_control_nodes:\n"
            "      hosts:\n"
            "        ctl-1:\n",
        )
        assert find_non_builtins_in_inventory(data) == []

    def test_structured_values_are_left_alone() -> None:
        # vm_spec/network-style composites are inventory data by design.
        data = _load(
            "all:\n"
            "  hosts:\n"
            "    vm-1:\n"
            "      network:\n"
            "        vlan_id: 80\n",
        )
        assert find_non_builtins_in_inventory(data) == []

    def test_walks_nested_children() -> None:
        data = _load(
            "all:\n"
            "  children:\n"
            "    linux:\n"
            "      children:\n"
            "        debian:\n"
            "          hosts:\n"
            "            d-1:\n"
            "              stray_var: 1\n",
        )
        assert find_non_builtins_in_inventory(data) == [("host 'd-1'", "stray_var", 8)]

    def test_tolerates_bare_host_entries() -> None:
        assert find_non_builtins_in_inventory(_load("all:\n  hosts:\n    h:\n")) == []

    # --- inventory_vars_dir() ----------------------------------------------

    def test_vars_dir_detected() -> None:
        p = Path("/r/inventory/group_vars/proxmox/main.yml")
        assert inventory_vars_dir(p) == "group_vars"
        p = Path("/r/inventory/host_vars/h/main.yml")
        assert inventory_vars_dir(p) == "host_vars"

    def test_role_vars_are_not_inventory_vars() -> None:
        assert inventory_vars_dir(Path("/r/roles/myrole/vars/main.yml")) is None

    # --- matchyaml() -------------------------------------------------------

    def _lint(tmp_path: Any, rel: str, text: str) -> list[str]:
        from ansiblelint.file_utils import Lintable

        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return [
            m.message
            for m in InventoryVarPlacementRule().matchyaml(Lintable(str(path)))
        ]

    def test_matchyaml_group_vars_builtin(tmp_path: Any) -> None:
        messages = _lint(
            tmp_path,
            "inventory/group_vars/proxmox/main.yml",
            "---\nansible_user: root\n",
        )
        assert len(messages) == 1
        assert "ansible_user" in messages[0]

    def test_matchyaml_skips_role_vars(tmp_path: Any) -> None:
        assert (
            _lint(tmp_path, "roles/myrole/vars/main.yml", "---\nansible_user: root\n")
            == []
        )

    def test_matchyaml_honors_noqa(tmp_path: Any) -> None:
        assert (
            _lint(
                tmp_path,
                "inventory/group_vars/proxmox/main.yml",
                "---\nansible_user: root # noqa: inventory-var-placement\n",
            )
            == []
        )

    def test_matchyaml_inventory_direction(tmp_path: Any) -> None:
        messages = _lint(
            tmp_path,
            "inventory/hosts.yml",
            "all:\n  hosts:\n    web-1:\n      stray_var: 1\n",
        )
        assert len(messages) == 1
        assert "stray_var" in messages[0]
