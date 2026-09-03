# ansible-lint-rules

Custom [ansible-lint](https://ansible.readthedocs.io/projects/lint/) rules,
shared across repositories with `git subtree` so every consumer runs the same
copy.

## Rules

| Rule | Autofix | What it does |
| --- | --- | --- |
| `become-first` | yes | `become` and its `become_*` companions must sort directly after `name` in a task. |
| `no-host-os-vars` | no | A host entry in an inventory file must not declare `os_family`, `os_distribution`, `os_version` or `os_edition`. |
| `no-fake-ansible-vars` | no | Only Ansible's own built-in variables may use the `ansible_` prefix. |
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

The `ansible_` prefix belongs to Ansible. A variable that wears it without being
one of Ansible's built-ins reads as connection configuration to everyone who
meets it:

```yaml
# group_vars/control_nodes/main.yml
ansible_ssh_notify_email: ops@example.net   # flagged — not a built-in
ansible_ssh_common_args: -o ProxyJump=bast  # not flagged — genuinely built-in
notify_email: ops@example.net               # the fix
```

A role may prefix its own variables with its own name, so a role called
`ansible_control_node` setting `ansible_control_node_stage` is exempt — that is
the Galaxy flat-role-prefix convention, and `var-naming[no-role-prefix]` would
complain if it did anything else.

### `inventory-var-placement`

Two directions, decided by the same list:

```yaml
# group_vars/proxmox/main.yml
ansible_user: root      # flagged — a built-in, so it belongs in the inventory file

# inventory/hosts.yml
all:
  hosts:
    web-1:
      ansible_host: 10.0.0.1   # correct
      app_release_channel: beta  # flagged — not a built-in, belongs in host_vars/
```

The point is that a host's connection settings should be readable in one file
rather than reconstructed from group-merge precedence — which resolves by group
depth, then alphabetically, and in which `group_vars/*` outranks a `vars:` block
in the inventory file.

Group *names* are never treated as variables, structured values (a `vm_spec:`
mapping, say) are left alone, and role `vars/` directories are out of scope even
though they share ansible-lint's `vars` file kind.

## How the built-in list is derived

`no-fake-ansible-vars` and `inventory-var-placement` both ask "is this one of
Ansible's own variables?", so the answer lives once in `ansible_builtin_vars.py`.
It is **not** an `ansible_` prefix test, which is wrong in both directions: it
flags homelab names that merely look built-in, and it misses real ones that carry
no prefix at all (`become`, `proxmox_api_host`, `wsl_user`).

The list is the union of three sources in ansible-core — `MAGIC_VARIABLE_MAPPING`,
base config settings with a `vars:` entry (the only source of
`ansible_python_interpreter`), and `vars:` entries on every connection/become/shell
plugin option harvested through `ansible-doc`. `ansible-doc` is used rather than
`config.get_configuration_definitions()` because that function cannot see plugins
shipped in collections, and would omit e.g. `ansible_network_cli_ssh_type`.

Regenerate with the collections you care about installed:

```bash
python ansible_builtin_vars.py     # prints a replacement BUILTIN_VARS block
```

Because source 3 depends on installed collections, the committed list is a
*superset* of any one environment. The test asserts that invariant rather than
equality, so a machine with fewer collections still passes while a core upgrade
that adds a new variable fails.

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
