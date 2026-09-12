"""Discover the role names whose `<name>_` variable prefix is legitimate.

Both var rules need to know "is `ansible_control_node_stage` a role's own
variable, or a homelab var wearing Ansible's prefix?". The answer is a fact
about the environment, not about the string: it depends on whether a role by
that name actually exists.

WHY roles_path AND NOT A PATH HEURISTIC
---------------------------------------
An earlier version inferred the role from the file's own path — "a `vars/`
directory whose grandparent is `roles/`". That is wrong twice over:

* A PLAYBOOK may have its own `vars/` directory, so
  `playbooks/proxmox/lxc/vars/ansible_control_node.yml` was read as a role
  named `lxc`, and every variable in it was reported.
* A vars file that configures a role from OUTSIDE the role — the case above,
  named after the role it configures — has no role in its path at all, yet its
  variables are that role's and must carry its prefix.

Reading Ansible's own `roles_path` answers both, because it asks what roles
exist rather than guessing from where a file sits. `ansible.cfg` is the
authority on that, and `ansible-lint` has already loaded it.

`roles_path` is NOT on its own sufficient, which is the subtle part. Its DEFAULT
value is `~/.ansible/roles`, `/usr/share/ansible/roles`, `/etc/ansible/roles` —
the project's own `roles/` is absent unless an `ansible.cfg` explicitly appends
it. Ansible normally reaches a project's roles by playbook adjacency instead. So
local `roles/` directories are scanned too: the one at the project root, and any
nested under it (`playbooks/<area>/roles/<name>/`). Without the root one, a role
called `ansible_myapp` goes undiscovered in any repo whose `ansible.cfg` does not
append `./roles`, and its own correctly-prefixed `ansible_myapp_port` is then
reported as a fake built-in.
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path

# A directory is a role if it holds at least one of these.
ROLE_MARKERS: frozenset[str] = frozenset(
    {"defaults", "tasks", "vars", "handlers", "meta"},
)


def _is_role_dir(path: Path) -> bool:
    try:
        return path.is_dir() and any(
            (path / marker).is_dir() for marker in ROLE_MARKERS
        )
    except OSError:  # pragma: no cover - unreadable path
        return False


def roles_in(directory: Path) -> set[str]:
    """Return the names of role directories directly inside `directory`."""
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return set()
    return {entry.name for entry in entries if _is_role_dir(entry)}


def configured_roles_path() -> list[Path]:
    """Return `roles_path` as Ansible itself resolves it.

    Falls back to an empty list when ansible-core is not importable, so the
    rules degrade to "no role prefixes are exempt" rather than crashing.
    """
    try:
        from ansible import constants as c
    except ImportError:  # pragma: no cover - ansible-core is a hard dep of lint
        return []
    return [Path(entry) for entry in (c.DEFAULT_ROLES_PATH or [])]


def local_roles_dirs(root: Path, *, max_depth: int = 4) -> list[Path]:
    """Return `roles/` directories inside the project that roles_path may miss.

    Two sources, and the first is easy to forget:

    * `<root>/roles` itself. The default `roles_path` does NOT include it, so a
      repo that has not appended `./roles` in `ansible.cfg` would otherwise have
      every one of its own roles go undiscovered.
    * `roles/` nested further down, e.g. `playbooks/<area>/roles/`. Ansible
      resolves those relative to the playbook that uses them, so they are real
      roles that `roles_path` never mentions.

    Depth-limited: this runs once per project and must not walk a whole
    repository.
    """
    found: list[Path] = []
    project_roles = root / "roles"
    if project_roles.is_dir():
        found.append(project_roles)
    for depth in range(1, max_depth + 1):
        pattern = "/".join(["*"] * depth) + "/roles"
        try:
            found.extend(path for path in root.glob(pattern) if path.is_dir())
        except OSError:  # pragma: no cover
            continue
    return found


@functools.lru_cache(maxsize=8)
def known_role_names(project_root: str | None = None) -> frozenset[str]:
    """Return every role name visible to this project.

    Cached: the answer is a property of the environment, and recomputing it per
    linted file would stat the same directories thousands of times.
    """
    names: set[str] = set()
    for directory in configured_roles_path():
        names |= roles_in(directory)
    if project_root:
        root = Path(project_root)
        for directory in local_roles_dirs(root):
            names |= roles_in(directory)
    return frozenset(names)


def owns_prefix(name: str, owners: frozenset[str] | set[str]) -> bool:
    """True if `name` is `<owner>_<something>` for one of `owners`.

    The separator is required, so a role called `ansible_control` does not
    excuse `ansible_controlnode_x`.
    """
    return any(name.startswith(f"{owner}_") for owner in owners)


if "pytest" in sys.modules:  # pragma: no cover
    import pytest

    @pytest.fixture
    def role_tree(tmp_path: Path) -> Path:
        for role, marker in (
            ("ansible_control_node", "defaults"),
            ("ansible_builder", "vars"),
            ("shell_config", "tasks"),
        ):
            (tmp_path / "roles" / role / marker).mkdir(parents=True)
        # Not a role: no marker subdirectory.
        (tmp_path / "roles" / "not_a_role").mkdir(parents=True)
        return tmp_path

    def test_roles_in_finds_marker_dirs(role_tree: Path) -> None:
        assert roles_in(role_tree / "roles") == {
            "ansible_control_node",
            "ansible_builder",
            "shell_config",
        }

    def test_roles_in_skips_dir_without_markers(role_tree: Path) -> None:
        assert "not_a_role" not in roles_in(role_tree / "roles")

    def test_roles_in_tolerates_missing_dir(tmp_path: Path) -> None:
        assert roles_in(tmp_path / "nope") == set()

    def test_playbook_adjacent_roles_found(tmp_path: Path) -> None:
        (tmp_path / "playbooks" / "area" / "roles" / "local_role" / "tasks").mkdir(
            parents=True,
        )
        names: set[str] = set()
        for d in local_roles_dirs(tmp_path):
            names |= roles_in(d)
        assert "local_role" in names

    def test_project_root_roles_dir_found(tmp_path: Path) -> None:
        """Regression: the default roles_path does NOT include <root>/roles.

        Missing it made a role's own correctly-prefixed variable look fake in
        any repo that has not appended ./roles to roles_path in ansible.cfg.
        """
        (tmp_path / "roles" / "ansible_myapp" / "defaults").mkdir(parents=True)
        assert tmp_path / "roles" in local_roles_dirs(tmp_path)
        names: set[str] = set()
        for d in local_roles_dirs(tmp_path):
            names |= roles_in(d)
        assert "ansible_myapp" in names

    def test_root_and_nested_roles_dirs_both_found(tmp_path: Path) -> None:
        (tmp_path / "roles" / "root_role" / "tasks").mkdir(parents=True)
        (tmp_path / "playbooks" / "roles" / "nested_role" / "tasks").mkdir(
            parents=True,
        )
        names: set[str] = set()
        for d in local_roles_dirs(tmp_path):
            names |= roles_in(d)
        assert {"root_role", "nested_role"} <= names

    def test_known_role_names_includes_project_root_roles(tmp_path: Path) -> None:
        (tmp_path / "roles" / "ansible_myapp" / "defaults").mkdir(parents=True)
        known_role_names.cache_clear()
        assert "ansible_myapp" in known_role_names(str(tmp_path))

    def test_local_roles_dirs_tolerates_missing_root_roles(tmp_path: Path) -> None:
        assert local_roles_dirs(tmp_path) == []

    def test_configured_roles_path_is_a_list() -> None:
        # Environment-dependent, so assert only the contract.
        assert isinstance(configured_roles_path(), list)
        assert all(isinstance(p, Path) for p in configured_roles_path())

    def test_owns_prefix_requires_separator() -> None:
        assert owns_prefix("ansible_control_node_stage", {"ansible_control_node"})
        assert not owns_prefix("ansible_controlnode_x", {"ansible_control"})
        assert not owns_prefix("ansible_user", {"ansible_control_node"})

    def test_owns_prefix_empty_owners() -> None:
        assert not owns_prefix("ansible_anything", set())
