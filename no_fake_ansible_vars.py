"""Custom ansible-lint rule: no homelab vars wearing an `ansible_` prefix.

Convention: the `ansible_` prefix belongs to Ansible. A variable that starts
with it and is NOT one of Ansible's built-in behavioral/connection vars is
misleading — it reads as connection configuration to everyone who meets it, and
in a repo that also enforces "built-in vars live in the inventory file" it reads
as a convention violation on top.

The case this was written for: `ansible_ssh_notify_email`, a notification
address, sitting in `group_vars/` directly alongside the genuinely reserved
`ansible_ssh_common_args`. Nothing about the name told a reader which of the two
it was.

WHAT IT DOES NOT DO
-------------------
It does not test the prefix alone. Membership is checked against
`BUILTIN_ANSIBLE_VARS`, harvested from ansible-core itself — see
`ansible_builtin_vars.py` for why a prefix test is wrong in both directions.

OWNER-PREFIX EXEMPTION
----------------------
A role named `ansible_control_node` is *supposed* to prefix its variables
`ansible_control_node_*` — that is the Galaxy flat-role-prefix convention, and
ansible-lint's own `var-naming[no-role-prefix]` would complain if it did
anything else. A name is therefore exempt when it starts with the name of
whatever owns the file: the enclosing role, or the file's own stem, which covers
a vars file named after the role it configures (`vars/ansible_control_node.yml`)
without that file living inside the role. Both are anchored to the path, so the
exemption cannot be borrowed by an unrelated file.

Scope: variable DEFINITIONS in vars-shaped files — role `defaults/` and `vars/`,
`group_vars/`, `host_vars/`, and standalone vars files. Group `vars:` blocks
inside an inventory file are covered by `inventory-var-placement` instead, which
already walks that structure; doing it here too would double-report.

Not autofix-capable: renaming a variable requires updating every reader, which
is not a transform this rule can see, let alone make safely.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ansiblelint.errors import MatchError
from ansiblelint.rules import AnsibleLintRule
from ansiblelint.skip_utils import get_rule_skips_from_line

try:  # pragma: no cover - import shape differs between rulesdir and package use
    from ansible_builtin_vars import BUILTIN_ANSIBLE_VARS
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).parent))
    from ansible_builtin_vars import BUILTIN_ANSIBLE_VARS

if TYPE_CHECKING:
    from ansiblelint.file_utils import Lintable

TAG = "no-fake-ansible-vars[naming]"


def enclosing_role(path: Path) -> str | None:
    """Return the role name if `path` sits inside a role, else None.

    A role is `<...>/roles/<name>/{defaults,vars,tasks,handlers,meta}/...`. The
    `roles/` ancestor is required, not just the role-shaped subdirectory: a
    PLAYBOOK may also have a `vars/` directory, and matching on the subdirectory
    alone read `playbooks/proxmox/lxc/vars/foo.yml` as a role named `lxc`.
    """
    role_subdirs = {"defaults", "vars", "tasks", "handlers", "meta"}
    for parent in path.parents:
        if (
            parent.name in role_subdirs
            and parent.parent != parent
            and parent.parent.parent.name == "roles"
        ):
            return parent.parent.name
    return None


def owner_prefixes(path: Path) -> set[str]:
    """Return the names whose `<name>_` prefix this file may legitimately use.

    Two owners, both conventional:

    * The enclosing role. A role called `ansible_control_node` is *supposed* to
      name its variables `ansible_control_node_*`.
    * The file's own stem, for a vars file named after the role it configures —
      `playbooks/<area>/vars/ansible_control_node.yml` carries that role's
      variables without living inside the role.
    """
    owners = {path.stem}
    role = enclosing_role(path)
    if role:
        owners.add(role)
    return owners


def find_fake_ansible_vars(
    data: Any,
    owners: set[str] | None = None,
) -> list[tuple[str, int]]:
    """Return (varname, line) for each top-level `ansible_*` non-built-in.

    Only TOP-LEVEL keys are considered. A nested key is a field inside somebody
    else's data structure, not a variable Ansible will ever resolve by that
    name, so flagging it would be a false positive.
    """
    if not isinstance(data, dict):
        return []

    def line_of(node: Any, key: str) -> int:
        lc = getattr(node, "lc", None)
        if lc is None or not hasattr(lc, "data"):
            return 0
        pos = lc.data.get(key)
        return pos[0] + 1 if pos else 0

    found: list[tuple[str, int]] = []
    for key in data:
        name = str(key)
        if not name.startswith("ansible_"):
            continue
        if name in BUILTIN_ANSIBLE_VARS:
            continue
        # A role (or a vars file named after one) may prefix its own vars with
        # that name.
        if any(name.startswith(f"{owner}_") for owner in owners or ()):
            continue
        found.append((name, line_of(data, key)))
    return found


class NoFakeAnsibleVarsRule(AnsibleLintRule):
    """Only Ansible's own built-in variables may use the ansible_ prefix."""

    id = "no-fake-ansible-vars"
    severity = "MEDIUM"
    tags = ["idiom"]
    version_changed = "1.1.0"
    _ids = {TAG: "ansible_-prefixed name is not an Ansible built-in"}

    def matchyaml(self, file: Lintable) -> list[MatchError]:
        if str(file.kind) != "vars":
            return []

        from ruamel.yaml import YAML
        from ruamel.yaml.error import YAMLError

        try:
            data = YAML(typ="rt").load(file.content)
        except YAMLError:  # pragma: no cover - malformed YAML is load-failure's job
            return []

        owners = owner_prefixes(Path(str(file.path)))
        lines = file.content.splitlines()

        def skipped(lineno: int) -> bool:
            if not 0 < lineno <= len(lines):
                return False
            skips = get_rule_skips_from_line(lines[lineno - 1], file, lineno)
            return bool({self.id, TAG}.intersection(skips))

        return [
            self.create_matcherror(
                f"'{name}' uses the ansible_ prefix but is not one of Ansible's "
                "built-in variables, so it reads as connection configuration "
                "when it is not. Rename it — e.g. drop the prefix, or use the "
                "role's own name as the prefix.",
                filename=file,
                lineno=line,
                tag=TAG,
            )
            for name, line in find_fake_ansible_vars(data, owners)
            if not skipped(line)
        ]


if "pytest" in sys.modules:  # pragma: no cover
    from ruamel.yaml import YAML

    def _load(text: str) -> Any:
        return YAML(typ="rt").load(text)

    # --- find_fake_ansible_vars() -----------------------------------------

    def test_flags_a_fake_builtin() -> None:
        data = _load("---\nansible_ssh_notify_email: a@b.net\n")
        assert find_fake_ansible_vars(data) == [("ansible_ssh_notify_email", 2)]

    def test_allows_a_real_builtin() -> None:
        assert find_fake_ansible_vars(_load("---\nansible_user: root\n")) == []

    def test_allows_a_collection_provided_builtin() -> None:
        # Regression: harvested via ansible-doc, invisible to
        # config.get_configuration_definitions(). A naive list would flag it.
        data = _load("---\nansible_network_cli_ssh_type: libssh\n")
        assert find_fake_ansible_vars(data) == []

    def test_allows_an_unprefixed_name() -> None:
        assert find_fake_ansible_vars(_load("---\nemail_recipient: a@b.net\n")) == []

    def test_role_prefix_exemption() -> None:
        data = _load("---\nansible_control_node_stage: build\n")
        assert find_fake_ansible_vars(data, {"ansible_control_node"}) == []
        # ...but only for the role that owns the prefix.
        assert find_fake_ansible_vars(data, {"other_role"}) == [
            ("ansible_control_node_stage", 2),
        ]

    def test_role_exemption_requires_the_separator() -> None:
        # `ansible_controlnode_x` must not be excused by role `ansible_control`.
        data = _load("---\nansible_controlnode_x: 1\n")
        assert find_fake_ansible_vars(data, {"ansible_control"}) == [
            ("ansible_controlnode_x", 2),
        ]

    def test_ignores_nested_keys() -> None:
        data = _load("---\nmy_config:\n  ansible_bogus: 1\n")
        assert find_fake_ansible_vars(data) == []

    def test_tolerates_empty_and_non_mapping() -> None:
        assert find_fake_ansible_vars(_load("---\n{}\n")) == []
        assert find_fake_ansible_vars(_load("---\n- a\n- b\n")) == []

    # --- enclosing_role() --------------------------------------------------

    def test_enclosing_role_from_defaults() -> None:
        p = Path("/repo/roles/ansible_control_node/defaults/main.yml")
        assert enclosing_role(p) == "ansible_control_node"

    def test_enclosing_role_from_vars() -> None:
        assert enclosing_role(Path("/repo/roles/myrole/vars/RedHat.yml")) == "myrole"

    def test_enclosing_role_none_for_group_vars() -> None:
        p = Path("/repo/inventory/group_vars/ansible_control_nodes/main.yml")
        assert enclosing_role(p) is None

    def test_playbook_vars_dir_is_not_a_role() -> None:
        # Regression: a playbook may have its own vars/ directory. Reading the
        # subdirectory alone made this look like a role named "lxc".
        p = Path("/repo/playbooks/proxmox/lxc/vars/ansible_control_node.yml")
        assert enclosing_role(p) is None

    def test_roles_dir_under_playbooks_still_counts() -> None:
        p = Path("/repo/playbooks/area/roles/myrole/defaults/main.yml")
        assert enclosing_role(p) == "myrole"

    # --- owner_prefixes() --------------------------------------------------

    def test_owner_prefixes_include_file_stem() -> None:
        # A vars file named after the role it configures owns that prefix.
        p = Path("/repo/playbooks/proxmox/lxc/vars/ansible_control_node.yml")
        assert owner_prefixes(p) == {"ansible_control_node"}

    def test_owner_prefixes_include_role_and_stem() -> None:
        p = Path("/repo/roles/ansible_builder/vars/Debian.yml")
        assert owner_prefixes(p) == {"ansible_builder", "Debian"}

    # --- matchyaml() -------------------------------------------------------

    def _lint(tmp_path: Any, rel: str, text: str) -> list[str]:
        from ansiblelint.file_utils import Lintable

        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return [
            m.message for m in NoFakeAnsibleVarsRule().matchyaml(Lintable(str(path)))
        ]

    def test_matchyaml_reports_group_vars(tmp_path: Any) -> None:
        messages = _lint(
            tmp_path,
            "inventory/group_vars/ctl/main.yml",
            "---\nansible_ssh_notify_email: a@b.net\n",
        )
        assert len(messages) == 1
        assert "ansible_ssh_notify_email" in messages[0]

    def test_matchyaml_exempts_role_own_prefix(tmp_path: Any) -> None:
        assert (
            _lint(
                tmp_path,
                "roles/ansible_control_node/defaults/main.yml",
                "---\nansible_control_node_stage: build\n",
            )
            == []
        )

    def test_matchyaml_exempts_playbook_vars_file_named_for_a_role(
        tmp_path: Any,
    ) -> None:
        # Regression: these are the role's variables, set outside the role.
        assert (
            _lint(
                tmp_path,
                "playbooks/proxmox/lxc/vars/ansible_control_node.yml",
                "---\nansible_control_node_lxc_vmid: 2008\n",
            )
            == []
        )

    def test_matchyaml_still_flags_an_unrelated_prefix_in_that_dir(
        tmp_path: Any,
    ) -> None:
        assert (
            len(
                _lint(
                    tmp_path,
                    "playbooks/proxmox/lxc/vars/git_server.yml",
                    "---\nansible_bogus_thing: 1\n",
                ),
            )
            == 1
        )

    def test_matchyaml_honors_noqa(tmp_path: Any) -> None:
        assert (
            _lint(
                tmp_path,
                "inventory/group_vars/ctl/main.yml",
                "---\nansible_legacy_thing: 1 # noqa: no-fake-ansible-vars\n",
            )
            == []
        )

    def test_matchyaml_skips_non_vars_files(tmp_path: Any) -> None:
        from ansiblelint.file_utils import Lintable

        path = tmp_path / "inventory" / "hosts.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("all:\n  hosts:\n    h:\n")
        lintable = Lintable(str(path))
        assert str(lintable.kind) != "vars"
        assert NoFakeAnsibleVarsRule().matchyaml(lintable) == []
