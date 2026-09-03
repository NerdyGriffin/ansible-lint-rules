# ansible-lint-rules

Custom [ansible-lint](https://ansible.readthedocs.io/projects/lint/) rules,
shared across repositories with `git subtree` so every consumer runs the same
copy.

## Rules

| Rule | Autofix | What it does |
| --- | --- | --- |
| `become-first` | yes | `become` and its `become_*` companions must sort directly after `name` in a task. |
| `no-host-os-vars` | no | A host entry in an inventory file must not declare `os_family`, `os_distribution`, `os_version` or `os_edition`. |
| `no-fake-ansible-vars` | no | A vars file must not define `ansible_`-prefixed variables. |
| `inventory-var-placement` | no | Built-in connection vars belong in the inventory file; everything else belongs in `group_vars`/`host_vars`. |

These are opinionated conventions, not bug detectors. Adopt the ones you want;
`skip_list` disables the rest, or `warn_list` keeps them running but makes their
findings non-fatal.

### `become-first`

```yaml
# Fails
- name: Install the package
  ansible.builtin.apt:
    name: htop
  become: true

# Passes
- name: Install the package
  become: true
  ansible.builtin.apt:
    name: htop
```

`ansible-lint --fix` hoists the `become` group automatically. Every other key
keeps its relative order, so the transform touches nothing else.

### `no-host-os-vars`

Per-host OS metadata duplicates gathered facts and drifts silently. Read
`ansible_facts['os_family']` instead, or branch on inventory group membership
when the host does not exist yet at render time.

```yaml
all:
  hosts:
    web-1:
      os_family: RedHat          # flagged
      hyperv_guest_config:
        base_images:
          server2025:
            os_version: '2025'   # not flagged — different namespace
```

Scope is deliberately narrow: only keys set directly on a host entry under a
`hosts:` mapping in an inventory file. For a device that genuinely cannot gather
facts (a switch, a UPS card), record the OS in a comment, or use
`# noqa: no-host-os-vars` if it must be a var.

### `no-fake-ansible-vars`

In a vars file — `group_vars/`, `host_vars/`, a role's `defaults/` or `vars/` —
a name starting with `ansible_` is wrong whichever kind it turns out to be, so
this rule matches on the **prefix**:

```yaml
# group_vars/control_nodes/main.yml
ansible_user: root                        # [misplaced] — a built-in; belongs in the inventory file
ansible_ssh_notify_email: ops@example.net # [naming]    — not a built-in; rename it
notify_email: ops@example.net             # fine
```

The built-in list is still consulted, but only to decide *which* of the two
problems it is, so the message names the right fix — move it, or rename it.

Inventory files are out of scope: `ansible_` names are correct in `hosts.yml`,
and the opposite question there belongs to `inventory-var-placement`.

A role may prefix its own variables with its own name, so a role called
`ansible_control_node` setting `ansible_control_node_stage` is exempt — that is
the Galaxy flat-role-prefix convention. Which names count is read from Ansible's
live `roles_path` (see below), not guessed from the file's path.

### `inventory-var-placement`

Two directions, decided by the built-in list:

```yaml
# group_vars/proxmox/main.yml
become: false            # flagged — a built-in (no prefix!), belongs in the inventory file

# inventory/hosts.yml
all:
  hosts:
    web-1:
      ansible_host: 10.0.0.1     # correct
      app_release_channel: beta  # flagged — not a built-in, belongs in host_vars/
```

The point is that a host's connection settings should be readable in one file
rather than reconstructed from group-merge precedence — which resolves by group
depth, then alphabetically, and in which `group_vars/*` outranks a `vars:` block
in the inventory file.

Group *names* are never treated as variables, structured values (a `vm_spec:`
mapping, say) are left alone, and role `vars/` directories are out of scope even
though they share ansible-lint's `vars` file kind.

**No line draws findings from two of these rules.** `no-fake-ansible-vars` owns
`ansible_`-prefixed names in vars files, so this rule reports only *unprefixed*
built-ins there. `no-host-os-vars` owns the `os_*` keys, so this rule skips them
— not merely to avoid a duplicate, but because "move it to `group_vars`" is the
wrong fix for a var whose real remedy is deletion.

## How the built-in list is derived

`no-fake-ansible-vars` and `inventory-var-placement` both ask "is this one of
Ansible's own variables?", so the answer lives once in `ansible_builtin_vars.py`.
It is deliberately **not** an `ansible_` prefix test, which is wrong in both
directions: it flags homelab names that merely look built-in, and it misses real
ones that carry no prefix at all (`become`, `proxmox_api_host`, `wsl_user`).

The list is the union of three sources in ansible-core — `MAGIC_VARIABLE_MAPPING`,
base config settings with a `vars:` entry (the only source of
`ansible_python_interpreter`), and `vars:` entries on every connection/become/shell
plugin option harvested through `ansible-doc`. `ansible-doc` is used rather than
`config.get_configuration_definitions()` because that function cannot see plugins
shipped in collections, and would omit e.g. `ansible_network_cli_ssh_type` from
`ansible.netcommon.network_cli` — a real variable that would then be reported as
a fake one.

Regenerate with the collections you care about installed:

```bash
python ansible_builtin_vars.py     # prints a replacement BUILTIN_VARS block
```

Because the third source depends on installed collections, the committed list is
a *superset* of any one environment. The test asserts that invariant rather than
equality, so a machine with fewer collections still passes while a core upgrade
that adds a variable fails.

## How role prefixes are discovered

`role_prefixes.py` answers "does a role by this name actually exist?" from
Ansible's own **`roles_path`** (`ansible.constants.DEFAULT_ROLES_PATH`, which
honours `ansible.cfg`), plus any playbook-adjacent `roles/` directories, which
`roles_path` never lists because Ansible resolves those relative to the playbook.

Asking the environment beats inferring the role from the file's path, which was
wrong twice over:

* A **playbook** may have its own `vars/` directory, so
  `playbooks/proxmox/lxc/vars/ansible_control_node.yml` was read as a role named
  `lxc` — 32 false positives against a real repository.
* A vars file that configures a role from *outside* it has no role in its path at
  all, yet its variables are that role's and must carry that role's prefix.

## Use in a repository

Vendor this repo into `.ansible-lint-rules/` with `git subtree`:

```bash
git remote add lint-rules https://github.com/NerdyGriffin/ansible-lint-rules.git
git subtree add --prefix .ansible-lint-rules lint-rules main --squash
```

Then point `.ansible-lint` at the directory:

```yaml
rulesdir:
  - .ansible-lint-rules
```

The rules are committed into the consumer, so CI needs no extra step — it lints
with the vendored copy.

To get later changes:

```bash
git subtree pull --prefix .ansible-lint-rules lint-rules main --squash
```

To send a local fix back:

```bash
git subtree push --prefix .ansible-lint-rules lint-rules <branch>
```

## Tests

Each rule carries its smoke tests inside the module, behind
`if "pytest" in sys.modules:` — the upstream ansible-lint idiom. `pytest.ini`
collects them:

```bash
pip install ansible-lint pytest
pytest
```

## License

MIT
