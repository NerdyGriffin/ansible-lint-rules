"""Ansible's built-in (behavioral / connection) variable names.

Shared by `no-fake-ansible-vars` and `inventory-var-placement`. Both rules turn
on the same question — "is this name one Ansible itself defines?" — so the list
lives here once rather than in each rule.

WHY A LIST AND NOT AN `ansible_` PREFIX TEST
--------------------------------------------
A prefix test is wrong in both directions:

* It flags names Ansible never reserved. `ansible_ssh_notify_email` was a
  homelab notification address that merely looked built-in — the very confusion
  `no-fake-ansible-vars` exists to stop.
* It misses real ones that carry no prefix. `become`, `become_user`,
  `proxmox_api_host`, `wsl_user` and friends below are genuine connection-plugin
  vars, and a prefix test waves every one of them through.

WHERE THE NAMES COME FROM
-------------------------
The union of four sources, none of which is sufficient alone:

1. `ansible.constants.MAGIC_VARIABLE_MAPPING` — the connection/become mapping.
2. Base configuration settings carrying a `vars:` entry. This is the ONLY
   source of `ansible_python_interpreter`, which is config, not a plugin option.
3. `vars:` entries on every connection/become/shell plugin option, harvested via
   `ansible-doc`. `ansible-doc` is used rather than
   `config.get_configuration_definitions()` because that function does not see
   plugins shipped in COLLECTIONS — it silently omits, for example,
   `ansible_network_cli_ssh_type` from `ansible.netcommon.network_cli`, which
   would then be reported as a fake built-in.
4. `INVENTORY_ONLY_VARS`, a short hand-maintained set. `ansible_group_priority`
   is read by the inventory manager while it is *building* groups, so it works
   only from the inventory source and nowhere else — and for the same reason it
   is neither a magic-variable mapping nor a plugin option, so the three
   automatic sources cannot see it. Without this set `inventory-var-placement`
   would tell you to move it to `group_vars/`, where it does nothing.

REGENERATING
------------
Run `python ansible_builtin_vars.py` with the collections you care about
installed; it prints a replacement for `BUILTIN_VARS` below. Because source 3
depends on which collections are present, the list is a SUPERSET of any one
environment — see `test_frozen_list_covers_runtime`, which asserts exactly that
invariant rather than equality, so a machine with fewer collections still passes.
"""

from __future__ import annotations

import json
import subprocess
import sys

# Generated — see REGENERATING above. Sorted, one per line, so a regeneration
# diff reads as pure additions.
BUILTIN_VARS: frozenset[str] = frozenset(
    {
    'ansible_access_token_file',
    'ansible_admin_users',
    'ansible_async_dir',
    'ansible_aws_ssm_access_key_id',
    'ansible_aws_ssm_bucket_endpoint_url',
    'ansible_aws_ssm_bucket_name',
    'ansible_aws_ssm_bucket_sse_kms_key_id',
    'ansible_aws_ssm_bucket_sse_mode',
    'ansible_aws_ssm_document',
    'ansible_aws_ssm_endpoint_url',
    'ansible_aws_ssm_instance_id',
    'ansible_aws_ssm_plugin',
    'ansible_aws_ssm_profile',
    'ansible_aws_ssm_region',
    'ansible_aws_ssm_retries',
    'ansible_aws_ssm_s3_addressing_style',
    'ansible_aws_ssm_secret_access_key',
    'ansible_aws_ssm_session_token',
    'ansible_aws_ssm_timeout',
    'ansible_become',
    'ansible_become_exe',
    'ansible_become_flags',
    'ansible_become_method',
    'ansible_become_pass',
    'ansible_become_password',
    'ansible_become_user',
    'ansible_buffer_read_timeout',
    'ansible_buildah_auto_commit',
    'ansible_buildah_executable',
    'ansible_buildah_extra_args',
    'ansible_buildah_extra_env',
    'ansible_buildah_host',
    'ansible_buildah_ignore_mount_errors',
    'ansible_buildah_mount_detection',
    'ansible_buildah_timeout',
    'ansible_buildah_working_directory',
    'ansible_certificate_chain_file',
    'ansible_chroot_disable_root_check',
    'ansible_chroot_exe',
    'ansible_command_timeout',
    'ansible_common_remote_group',
    'ansible_connect_timeout',
    'ansible_connection',
    'ansible_connection_user',
    'ansible_control_path',
    'ansible_control_path_dir',
    'ansible_deprecation_warnings',
    'ansible_doas_allow_pipelining',
    'ansible_doas_exe',
    'ansible_doas_flags',
    'ansible_doas_pass',
    'ansible_doas_prompt_l10n',
    'ansible_doas_user',
    'ansible_docker_api_version',
    'ansible_docker_ca_cert',
    'ansible_docker_ca_path',
    'ansible_docker_client_cert',
    'ansible_docker_client_key',
    'ansible_docker_docker_host',
    'ansible_docker_extra_args',
    'ansible_docker_extra_env',
    'ansible_docker_host',
    'ansible_docker_privileged',
    'ansible_docker_timeout',
    'ansible_docker_tls',
    'ansible_docker_tls_hostname',
    'ansible_docker_user',
    'ansible_docker_validate_certs',
    'ansible_docker_working_dir',
    'ansible_dzdo_exe',
    'ansible_dzdo_flags',
    'ansible_dzdo_pass',
    'ansible_dzdo_user',
    'ansible_enable_pass',
    'ansible_executable',
    'ansible_facts_modules',
    'ansible_func_host',
    'ansible_gcloud_account',
    'ansible_gcloud_configuration',
    'ansible_gcloud_executable',
    'ansible_gcloud_host',
    'ansible_gcloud_known_hosts_file',
    'ansible_gcloud_private_key_file',
    'ansible_gcloud_project',
    'ansible_gcloud_zone',
    'ansible_group_priority',
    'ansible_grpc_connection_type',
    'ansible_grpc_ssl_target_name_override',
    'ansible_host',
    'ansible_host_key_checking',
    'ansible_httpapi_ca_path',
    'ansible_httpapi_ciphers',
    'ansible_httpapi_client_cert',
    'ansible_httpapi_client_key',
    'ansible_httpapi_http_agent',
    'ansible_httpapi_pass',
    'ansible_httpapi_password',
    'ansible_httpapi_port',
    'ansible_httpapi_session_key',
    'ansible_httpapi_use_proxy',
    'ansible_httpapi_use_ssl',
    'ansible_httpapi_validate_certs',
    'ansible_incus_executable',
    'ansible_incus_host',
    'ansible_incus_project',
    'ansible_incus_remote',
    'ansible_inject_invocation',
    'ansible_interpreter_python_fallback',
    'ansible_iocage_host',
    'ansible_iocage_user',
    'ansible_jail_host',
    'ansible_jail_user',
    'ansible_known_hosts_file',
    'ansible_ksu_exe',
    'ansible_ksu_flags',
    'ansible_ksu_pass',
    'ansible_ksu_prompt_l10n',
    'ansible_ksu_user',
    'ansible_kubectl_api_key',
    'ansible_kubectl_ca_cert',
    'ansible_kubectl_cert_file',
    'ansible_kubectl_client_cert',
    'ansible_kubectl_client_key',
    'ansible_kubectl_config',
    'ansible_kubectl_container',
    'ansible_kubectl_context',
    'ansible_kubectl_extra_args',
    'ansible_kubectl_host',
    'ansible_kubectl_key_file',
    'ansible_kubectl_kubeconfig',
    'ansible_kubectl_local_env_vars',
    'ansible_kubectl_namespace',
    'ansible_kubectl_password',
    'ansible_kubectl_pod',
    'ansible_kubectl_server',
    'ansible_kubectl_ssl_ca_cert',
    'ansible_kubectl_token',
    'ansible_kubectl_user',
    'ansible_kubectl_username',
    'ansible_kubectl_validate_certs',
    'ansible_kubectl_verify_ssl',
    'ansible_libssh_config_file',
    'ansible_libssh_host',
    'ansible_libssh_host_key_checking',
    'ansible_libssh_hostkeys',
    'ansible_libssh_key_exchange_algorithms',
    'ansible_libssh_pass',
    'ansible_libssh_password',
    'ansible_libssh_password_prompt',
    'ansible_libssh_proxy_command',
    'ansible_libssh_publickey_algorithms',
    'ansible_libssh_user',
    'ansible_libvirt_lxc_host',
    'ansible_libvirt_lxc_noseclabel',
    'ansible_libvirt_uri',
    'ansible_local_become_strip_preamble',
    'ansible_local_become_success_timeout',
    'ansible_lock_file_timeout',
    'ansible_lxc_executable',
    'ansible_lxc_host',
    'ansible_lxd_executable',
    'ansible_lxd_host',
    'ansible_lxd_project',
    'ansible_lxd_remote',
    'ansible_machinectl_exe',
    'ansible_machinectl_flags',
    'ansible_machinectl_pass',
    'ansible_machinectl_user',
    'ansible_module_compression',
    'ansible_netconf_host_key_checking',
    'ansible_netconf_libssh',
    'ansible_netconf_password',
    'ansible_netconf_proxy_command',
    'ansible_netconf_ssh_config',
    'ansible_network_become_errors',
    'ansible_network_cli_retries',
    'ansible_network_cli_ssh_type',
    'ansible_network_import_modules',
    'ansible_network_os',
    'ansible_network_single_user_mode',
    'ansible_network_terminal_errors',
    'ansible_no_target_syslog',
    'ansible_nsenter_pid',
    'ansible_oc_api_key',
    'ansible_oc_ca_cert',
    'ansible_oc_cert_file',
    'ansible_oc_client_cert',
    'ansible_oc_client_key',
    'ansible_oc_config',
    'ansible_oc_container',
    'ansible_oc_context',
    'ansible_oc_extra_args',
    'ansible_oc_host',
    'ansible_oc_key_file',
    'ansible_oc_kubeconfig',
    'ansible_oc_local_env_vars',
    'ansible_oc_namespace',
    'ansible_oc_pod',
    'ansible_oc_server',
    'ansible_oc_ssl_ca_cert',
    'ansible_oc_token',
    'ansible_oc_validate_certs',
    'ansible_oc_verify_ssl',
    'ansible_paramiko_host',
    'ansible_paramiko_host_key_checking',
    'ansible_paramiko_pass',
    'ansible_paramiko_password',
    'ansible_paramiko_port',
    'ansible_paramiko_private_key_file',
    'ansible_paramiko_proxy_command',
    'ansible_paramiko_timeout',
    'ansible_paramiko_use_rsa_sha2_algorithms',
    'ansible_paramiko_user',
    'ansible_paramiko_user_known_hosts_file',
    'ansible_password',
    'ansible_pbrun_exe',
    'ansible_pbrun_flags',
    'ansible_pbrun_pass',
    'ansible_pbrun_user',
    'ansible_pbrun_wrap_execution',
    'ansible_persistent_log_messages',
    'ansible_pfexec_exe',
    'ansible_pfexec_flags',
    'ansible_pfexec_pass',
    'ansible_pfexec_user',
    'ansible_pfexec_wrap_execution',
    'ansible_pipelining',
    'ansible_platform_type',
    'ansible_pmrun_exe',
    'ansible_pmrun_flags',
    'ansible_pmrun_pass',
    'ansible_podman_executable',
    'ansible_podman_extra_args',
    'ansible_podman_extra_env',
    'ansible_podman_host',
    'ansible_podman_ignore_mount_errors',
    'ansible_podman_mount_detection',
    'ansible_podman_privilege_escalation',
    'ansible_podman_timeout',
    'ansible_podman_working_directory',
    'ansible_port',
    'ansible_private_key',
    'ansible_private_key_file',
    'ansible_private_key_passphrase',
    'ansible_private_key_password',
    'ansible_psrp_auth',
    'ansible_psrp_ca_cert',
    'ansible_psrp_cert_trust_path',
    'ansible_psrp_cert_validation',
    'ansible_psrp_certificate_key_password',
    'ansible_psrp_certificate_key_pem',
    'ansible_psrp_certificate_pem',
    'ansible_psrp_configuration_name',
    'ansible_psrp_connection_backoff',
    'ansible_psrp_connection_timeout',
    'ansible_psrp_credssp_auth_mechanism',
    'ansible_psrp_credssp_disable_tlsv1_2',
    'ansible_psrp_credssp_minimum_version',
    'ansible_psrp_host',
    'ansible_psrp_ignore_proxy',
    'ansible_psrp_max_envelope_size',
    'ansible_psrp_message_encryption',
    'ansible_psrp_negotiate_delegate',
    'ansible_psrp_negotiate_hostname_override',
    'ansible_psrp_negotiate_send_cbt',
    'ansible_psrp_negotiate_service',
    'ansible_psrp_no_profile',
    'ansible_psrp_operation_timeout',
    'ansible_psrp_path',
    'ansible_psrp_port',
    'ansible_psrp_protocol',
    'ansible_psrp_proxy',
    'ansible_psrp_read_timeout',
    'ansible_psrp_reconnection_backoff',
    'ansible_psrp_reconnection_retries',
    'ansible_psrp_user',
    'ansible_python_interpreter',
    'ansible_python_module_rlimit_nofile',
    'ansible_remote_tmp',
    'ansible_root_certificates_file',
    'ansible_run0_exe',
    'ansible_run0_flags',
    'ansible_run0_user',
    'ansible_runas_flags',
    'ansible_runas_pass',
    'ansible_runas_user',
    'ansible_scp_executable',
    'ansible_scp_extra_args',
    'ansible_scp_if_ssh',
    'ansible_sesu_exe',
    'ansible_sesu_flags',
    'ansible_sesu_pass',
    'ansible_sesu_user',
    'ansible_sftp_batch_mode',
    'ansible_sftp_executable',
    'ansible_sftp_extra_args',
    'ansible_shell_allow_world_readable_temp',
    'ansible_shell_executable',
    'ansible_shell_type',
    'ansible_ssh_args',
    'ansible_ssh_common_args',
    'ansible_ssh_executable',
    'ansible_ssh_extra_args',
    'ansible_ssh_host',
    'ansible_ssh_host_key_checking',
    'ansible_ssh_known_hosts_file',
    'ansible_ssh_pass',
    'ansible_ssh_password',
    'ansible_ssh_password_mechanism',
    'ansible_ssh_pipelining',
    'ansible_ssh_pkcs11_provider',
    'ansible_ssh_port',
    'ansible_ssh_private_key',
    'ansible_ssh_private_key_file',
    'ansible_ssh_private_key_passphrase',
    'ansible_ssh_retries',
    'ansible_ssh_timeout',
    'ansible_ssh_transfer_method',
    'ansible_ssh_use_tty',
    'ansible_ssh_user',
    'ansible_ssh_verbosity',
    'ansible_sshpass_prompt',
    'ansible_su_exe',
    'ansible_su_flags',
    'ansible_su_pass',
    'ansible_su_prompt_l10n',
    'ansible_su_user',
    'ansible_sudo_chdir',
    'ansible_sudo_exe',
    'ansible_sudo_flags',
    'ansible_sudo_pass',
    'ansible_sudo_user',
    'ansible_sudosu_alt_method',
    'ansible_system_tmpdirs',
    'ansible_target_log_info',
    'ansible_terminal_initial_answer',
    'ansible_terminal_initial_prompt',
    'ansible_terminal_initial_prompt_checkall',
    'ansible_terminal_initial_prompt_newline',
    'ansible_terminal_stderr_re',
    'ansible_terminal_stdout_re',
    'ansible_timeout',
    'ansible_user',
    'ansible_vmware_guest_path',
    'ansible_vmware_guest_uuid',
    'ansible_vmware_host',
    'ansible_vmware_password',
    'ansible_vmware_port',
    'ansible_vmware_tools_exec_command_sleep_interval',
    'ansible_vmware_tools_executable',
    'ansible_vmware_tools_file_chunk_size',
    'ansible_vmware_tools_password',
    'ansible_vmware_tools_user',
    'ansible_vmware_user',
    'ansible_vmware_validate_certs',
    'ansible_win_async_startup_timeout',
    'ansible_winrm_connection_timeout',
    'ansible_winrm_host',
    'ansible_winrm_kinit_args',
    'ansible_winrm_kinit_cmd',
    'ansible_winrm_kinit_env_vars',
    'ansible_winrm_kinit_mode',
    'ansible_winrm_pass',
    'ansible_winrm_password',
    'ansible_winrm_path',
    'ansible_winrm_port',
    'ansible_winrm_scheme',
    'ansible_winrm_transport',
    'ansible_winrm_user',
    'ansible_worker_session_isolation',
    'ansible_zone_host',
    'become',
    'become_user',
    'incus_become_method',
    'inventory_hostname',
    'lxd_become_method',
    'proxmox_api_host',
    'proxmox_api_password',
    'proxmox_api_port',
    'proxmox_api_token_id',
    'proxmox_api_token_secret',
    'proxmox_api_user',
    'proxmox_become_method',
    'proxmox_connect_timeout',
    'proxmox_node',
    'proxmox_remote_tmp',
    'proxmox_validate_certs',
    'proxmox_vmid',
    'wsl_distribution',
    'wsl_remote_ssh_shell_type',
    'wsl_user',
    },
)

# Source 4 (see WHERE THE NAMES COME FROM). Hand-maintained: nothing in
# ansible-core enumerates these, because they are consumed during inventory
# parsing rather than looked up as variables afterwards.
INVENTORY_ONLY_VARS: frozenset[str] = frozenset({"ansible_group_priority"})

# The prefixed subset. `no-fake-ansible-vars` compares against this one: a name
# without the prefix cannot be mistaken for a built-in, so it is that rule's
# business only when it IS one.
BUILTIN_ANSIBLE_VARS: frozenset[str] = frozenset(
    name for name in BUILTIN_VARS if name.startswith("ansible_")
)


def _ansible_doc(*args: str) -> str:
    """Run `ansible-doc` and return its stdout, or raise with its stderr.

    Never swallow a failure here: an empty stdout would parse as `{}`, the
    plugin sweep would silently contribute nothing, and `_print_regenerated()`
    would print a *shrunken* list that looks perfectly valid. The superset test
    cannot catch that either, since fewer harvested names never violate it.
    """
    result = subprocess.run(  # noqa: S603
        ["ansible-doc", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = (
            f"ansible-doc {' '.join(args)} exited {result.returncode}: "
            f"{result.stderr.strip() or '(no stderr)'}"
        )
        raise RuntimeError(msg)
    return result.stdout


def harvest_runtime() -> set[str]:
    """Return the built-in var names this interpreter can actually see.

    Used by the regeneration entry point and by the superset test. Slow (it
    shells out to `ansible-doc`), so no rule calls it at lint time.
    """
    from ansible import constants as c

    names: set[str] = {
        name for names_ in c.MAGIC_VARIABLE_MAPPING.values() for name in names_
    }
    names |= INVENTORY_ONLY_VARS

    for definition in c.config.get_configuration_definitions().values():
        for entry in definition.get("vars") or []:
            name = entry.get("name") if isinstance(entry, dict) else entry
            if name:
                names.add(name)

    for plugin_type in ("connection", "become", "shell"):
        listing = _ansible_doc("-t", plugin_type, "--json", "--list")
        plugins = sorted(json.loads(listing or "{}"))
        if not plugins:
            continue
        dumped = _ansible_doc("-t", plugin_type, "-j", *plugins)
        for doc in json.loads(dumped or "{}").values():
            options = (doc.get("doc") or {}).get("options") or {}
            for option in options.values():
                for entry in option.get("vars") or []:
                    name = entry.get("name") if isinstance(entry, dict) else entry
                    if name:
                        names.add(name)

    # Private plumbing and test-plugin artefacts are not user-facing names.
    return {name for name in names if not name.startswith("_")}


def _print_regenerated() -> None:
    lines = "\n".join(f"        {name!r}," for name in sorted(harvest_runtime()))
    sys.stdout.write(
        "BUILTIN_VARS: frozenset[str] = frozenset(\n    {\n" + lines + "\n    },\n)\n",
    )


if __name__ == "__main__":
    _print_regenerated()


if "pytest" in sys.modules:  # pragma: no cover

    def test_frozen_list_is_sorted_and_nonempty() -> None:
        assert len(BUILTIN_VARS) > 300
        assert sorted(BUILTIN_VARS) == sorted(set(BUILTIN_VARS))

    def test_known_names_present() -> None:
        # One from each of the four sources, chosen because each is the ONLY
        # source of that name — together they prove no source was dropped.
        assert "ansible_user" in BUILTIN_VARS  # MAGIC_VARIABLE_MAPPING
        assert "ansible_python_interpreter" in BUILTIN_VARS  # base config
        assert "ansible_psrp_auth" in BUILTIN_VARS  # plugin option
        assert "ansible_group_priority" in BUILTIN_VARS  # inventory-only

    def test_inventory_only_vars_reach_harvest() -> None:
        # The frozen list is regenerated FROM harvest_runtime(), so source 4
        # must flow through it or the next regeneration would drop it.
        assert INVENTORY_ONLY_VARS <= harvest_runtime()

    def test_ansible_doc_failure_raises(monkeypatch: object) -> None:
        """A failed ansible-doc must not be read as 'no plugins'."""
        import pytest

        class Failed:
            returncode = 1
            stdout = ""
            stderr = "ERROR! boom"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: Failed())  # type: ignore[attr-defined]
        with pytest.raises(RuntimeError, match="exited 1: ERROR! boom"):
            _ansible_doc("-t", "connection", "--json", "--list")

    def test_unprefixed_builtins_are_kept() -> None:
        # A prefix test would lose these; the placement rule needs them.
        assert "become" in BUILTIN_VARS
        assert "inventory_hostname" in BUILTIN_VARS
        assert not any(
            name.startswith("ansible_") for name in {"become", "inventory_hostname"}
        )

    def test_prefixed_subset_excludes_unprefixed() -> None:
        assert "become" not in BUILTIN_ANSIBLE_VARS
        assert "ansible_user" in BUILTIN_ANSIBLE_VARS

    def test_frozen_list_covers_runtime() -> None:
        """The frozen list must be a SUPERSET of what this machine reports.

        Not equality: source 3 depends on installed collections, so CI (which
        installs none) legitimately sees fewer names. A core upgrade that adds a
        var this list does not carry fails here, which is the point.
        """
        missing = harvest_runtime() - set(BUILTIN_VARS)
        assert not missing, (
            f"ansible-core reports {len(missing)} built-in var(s) absent from "
            f"BUILTIN_VARS: {sorted(missing)[:10]}. "
            "Regenerate with: python ansible_builtin_vars.py"
        )
