"""Custom ansible-lint rule: no `ansible_`-prefixed variables in a vars file.

Convention: the `ansible_` prefix belongs to Ansible, and a vars file is not
where Ansible's own variables live. So in `group_vars/`, `host_vars/`, a role's
`defaults/` and `vars/`, or a standalone vars file, a name starting with
`ansible_` is wrong whichever kind it turns out to be:

* If it IS one of Ansible's built-ins, it is misplaced — connection settings
  belong in the inventory file so a host's reachability is readable in one place.
* If it is NOT, the name is misleading — it reads as connection configuration to
  everyone who meets it. The case this was written for is
  `ansible_ssh_notify_email`, a notification address, sitting directly beside the
  genuinely reserved `ansible_ssh_common_args`.

DELIBERATELY A PREFIX TEST
--------------------------
Unlike `inventory-var-placement`, this rule matches on the prefix rather than on
membership of the built-in list, because in a vars file BOTH answers are
findings. That makes it a cheap, obvious rule with an obvious remedy: no
`ansible_` names here.

The built-in list is still consulted, but only to say WHICH of the two problems
this is, so the message names the right fix — move it, or rename it.

`hosts.yml` and other inventory files are out of scope: `ansible_` names are
correct there, and the reverse question (a NON-built-in in the inventory file) is
`inventory-var-placement`'s to answer. The two rules therefore never both fire on
the same line.

OWNER-PREFIX EXEMPTION
----------------------
A role named `ansible_control_node` is supposed to prefix its variables
`ansible_control_node_*` — the Galaxy flat-role-prefix convention, which
ansible-lint's own `var-naming[no-role-prefix]` enforces from the other side. So
a name is exempt when it starts with the name of a role that ACTUALLY EXISTS,
discovered from Ansible's live `roles_path` rather than guessed from the file's
own path. See `role_prefixes.py` for why the path heuristic was wrong.

Not autofix-capable: renaming a variable means updating every reader, and moving
one between files changes its precedence rank. Neither is a transform this rule
can see, let alone make safely.
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
    from role_prefixes import known_role_names, owns_prefix
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).parent))
    from ansible_builtin_vars import BUILTIN_ANSIBLE_VARS
    from role_prefixes import known_role_names, owns_prefix

if TYPE_CHECKING:
    from ansiblelint.file_utils import Lintable

MISPLACED_TAG = "no-fake-ansible-vars[misplaced]"
NAMING_TAG = "no-fake-ansible-vars[naming]"


def find_prefixed_vars(
    data: Any,
    role_names: frozenset[str] | set[str] = frozenset(),
) -> list[tuple[str, int]]:
    """Return (varname, line) for each top-level `ansible_*` key.

    Only TOP-LEVEL keys count. A nested `ansible_user` is a field inside somebody
    else's data structure, not a variable Ansible resolves under that name.
    """
    if not isinstance(data, dict):
        return []

    def line_of(node: Any, key: Any) -> int:
        lc = getattr(node, "lc", None)
        if lc is None or not hasattr(lc, "data"):
            return 0
        pos = lc.data.get(key)
        return pos[0] + 1 if pos else 0

    return [
        (str(key), line_of(data, key))
        for key in data
        if str(key).startswith("ansible_") and not owns_prefix(str(key), role_names)
    ]


class NoFakeAnsibleVarsRule(AnsibleLintRule):
    """Vars files must not define ansible_-prefixed variables."""

    id = "no-fake-ansible-vars"
    severity = "MEDIUM"
    tags = ["idiom"]
    version_changed = "1.1.0"
    _ids = {
        MISPLACED_TAG: "built-in var belongs in the inventory file",
        NAMING_TAG: "ansible_-prefixed name is not an Ansible built-in",
    }

    def matchyaml(self, file: Lintable) -> list[MatchError]:
        if str(file.kind) != "vars":
            return []

        from ruamel.yaml import YAML
        from ruamel.yaml.error import YAMLError

        try:
            data = YAML(typ="rt").load(file.content)
        except YAMLError:  # pragma: no cover - malformed YAML is load-failure's job
            return []

        # cwd is the project root under ansible-lint; used only to find
        # playbook-adjacent roles/ dirs that roles_path does not cover.
        role_names = known_role_names(str(Path.cwd()))
        lines = file.content.splitlines()

        def skipped(lineno: int, tag: str) -> bool:
            if not 0 < lineno <= len(lines):
                return False
            skips = get_rule_skips_from_line(lines[lineno - 1], file, lineno)
            return bool({self.id, tag}.intersection(skips))

        matches: list[MatchError] = []
        for name, line in find_prefixed_vars(data, role_names):
            if name in BUILTIN_ANSIBLE_VARS:
                tag = MISPLACED_TAG
                message = (
                    f"'{name}' is one of Ansible's built-in connection variables, "
                    "so it belongs on the host entry or a group's vars: block in "
                    "the inventory file, not in a vars file. Keeping them in one "
                    "file is what makes a host's connection settings readable "
                    "without resolving group precedence."
                )
            else:
                tag = NAMING_TAG
                message = (
                    f"'{name}' uses the ansible_ prefix but is not one of "
                    "Ansible's built-in variables, so it reads as connection "
                    "configuration when it is not. Rename it — drop the prefix, "
                    "or use the owning role's name as the prefix."
                )
            if not skipped(line, tag):
                matches.append(
                    self.create_matcherror(
                        message,
                        filename=file,
                        lineno=line,
                        tag=tag,
                    ),
                )
        return matches


if "pytest" in sys.modules:  # pragma: no cover
    from ruamel.yaml import YAML

    def _load(text: str) -> Any:
        return YAML(typ="rt").load(text)

    # --- find_prefixed_vars() ---------------------------------------------

    def test_flags_a_fake_builtin() -> None:
        data = _load("---\nansible_ssh_notify_email: a@b.net\n")
        assert find_prefixed_vars(data) == [("ansible_ssh_notify_email", 2)]

    def test_flags_a_real_builtin_too() -> None:
        # The prefix test is the point: a built-in in a vars file is misplaced.
        assert find_prefixed_vars(_load("---\nansible_user: root\n")) == [
            ("ansible_user", 2),
        ]

    def test_ignores_unprefixed_names() -> None:
        assert find_prefixed_vars(_load("---\nemail_recipient: a@b.net\n")) == []

    def test_role_prefix_exemption() -> None:
        data = _load("---\nansible_control_node_stage: build\n")
        assert find_prefixed_vars(data, {"ansible_control_node"}) == []
        assert find_prefixed_vars(data, {"other_role"}) == [
            ("ansible_control_node_stage", 2),
        ]

    def test_role_exemption_requires_separator() -> None:
        data = _load("---\nansible_controlnode_x: 1\n")
        assert find_prefixed_vars(data, {"ansible_control"}) == [
            ("ansible_controlnode_x", 2),
        ]

    def test_ignores_nested_keys() -> None:
        assert find_prefixed_vars(_load("---\ncfg:\n  ansible_bogus: 1\n")) == []

    def test_tolerates_empty_and_non_mapping() -> None:
        assert find_prefixed_vars(_load("---\n{}\n")) == []
        assert find_prefixed_vars(_load("---\n- a\n")) == []

    # --- matchyaml() -------------------------------------------------------

    def _lint(tmp_path: Any, rel: str, text: str) -> list[Any]:
        from ansiblelint.file_utils import Lintable

        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return NoFakeAnsibleVarsRule().matchyaml(Lintable(str(path)))

    def test_matchyaml_tags_a_builtin_as_misplaced(tmp_path: Any) -> None:
        matches = _lint(
            tmp_path,
            "inventory/group_vars/proxmox/main.yml",
            "---\nansible_user: root\n",
        )
        assert len(matches) == 1
        assert matches[0].tag == MISPLACED_TAG
        assert "inventory file" in matches[0].message

    def test_matchyaml_tags_a_non_builtin_as_naming(tmp_path: Any) -> None:
        matches = _lint(
            tmp_path,
            "inventory/group_vars/ctl/main.yml",
            "---\nansible_ssh_notify_email: a@b.net\n",
        )
        assert len(matches) == 1
        assert matches[0].tag == NAMING_TAG
        assert "Rename it" in matches[0].message

    def test_matchyaml_honors_noqa(tmp_path: Any) -> None:
        assert (
            _lint(
                tmp_path,
                "inventory/group_vars/ctl/main.yml",
                "---\nansible_legacy: 1 # noqa: no-fake-ansible-vars\n",
            )
            == []
        )

    def test_matchyaml_exempts_a_role_in_project_root_roles(tmp_path: Any) -> None:
        """Regression: default roles_path excludes <root>/roles.

        A role's own correctly-prefixed variable was reported as a fake built-in
        in any repo that had not appended ./roles to roles_path in ansible.cfg.
        """
        import os

        from role_prefixes import known_role_names

        (tmp_path / "roles" / "ansible_myapp" / "defaults").mkdir(parents=True)
        (tmp_path / "roles" / "ansible_myapp" / "defaults" / "main.yml").write_text(
            "---\nansible_myapp_port: 8080\n",
        )
        known_role_names.cache_clear()
        cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            assert (
                _lint(
                    tmp_path,
                    "roles/ansible_myapp/defaults/main.yml",
                    "---\nansible_myapp_port: 8080\n",
                )
                == []
            )
        finally:
            os.chdir(cwd)
            known_role_names.cache_clear()

    def test_matchyaml_skips_inventory_files(tmp_path: Any) -> None:
        # hosts.yml is out of scope: ansible_ names are correct there.
        from ansiblelint.file_utils import Lintable

        path = tmp_path / "inventory" / "hosts.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("all:\n  hosts:\n    h:\n      ansible_host: 10.0.0.1\n")
        lintable = Lintable(str(path))
        assert str(lintable.kind) != "vars"
        assert NoFakeAnsibleVarsRule().matchyaml(lintable) == []
