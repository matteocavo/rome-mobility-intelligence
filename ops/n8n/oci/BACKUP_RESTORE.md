# Private backup and restore runbook

No commands here were run against a real instance. They require separate operator approval.
Use only operator-controlled encrypted output outside Git. GNU Privacy Guard (GPG) and Python
3 are free operator tools; no paid service is assumed. Do not upload backup material to CI.

## Backup (manual, initially daily and before every upgrade)

1. Unpublish the primary workflow, wait for any execution to finish, and keep Actions fallback
   disabled. Stop the n8n service; Caddy need not stop. Never copy live SQLite/WAL blindly.
2. Prepare a private output directory (0700) outside Git. Supply a separate strong backup
   passphrase file (0600) from the operator's protected storage, not the n8n encryption key.
3. Run the helper as an authorized Linux operator able to read the data and administer Docker:

```sh
docker compose --env-file /etc/rome-mobility-n8n/deployment.env -f ops/n8n/oci/compose.yaml stop n8n
python3 -m scripts.backup_n8n \
  --data-dir /var/lib/rome-mobility-n8n/n8n \
  --env-file /etc/rome-mobility-n8n/deployment.env \
  --passphrase-file /etc/rome-mobility-n8n/backup-passphrase \
  --output /home/OPERATOR/private-backups/n8n-DATE.tar.gz.gpg
```

The helper refuses a running Compose n8n service, output inside this Git checkout, nonprivate
output/passphrase permissions, existing output, links or special files. It uses SQLite's
backup API (including committed WAL) and streams a gzip TAR directly to GPG AES256; no plain
TAR is saved. The temporary SQLite snapshot is private and deleted afterward. The backup
contains metadata/workflows/encrypted credentials, other `.n8n` regular files and allowlisted
nonsecret deployment.env. The key-bearing `.n8n/config` is excluded; its remaining settings
are stored as `nonsecret-instance-settings.json`, never an incomplete live config.
The snapshot is consistent only under the documented single stopped writer assumption.

4. Copy the encrypted file to the operator's protected local backup storage, separate from
   the VM. Keep the exact Git revision/image lock alongside it; never commit the backup.
5. Back up **N8N_ENCRYPTION_KEY separately** in protected offline/password-manager storage.
   Verify access to both key and backup passphrase. Losing either can prevent recovery.
6. If restarting the old instance, leave schedules unpublished until the exclusivity rule
   has been checked. A process restart is not authorization to publish a schedule.

Optional: a second encrypted copy can use OCI Object Storage Always Free, but only after the
operator verifies current entitlement, storage/request/egress limits and no paid tiers. This
is not required or configured. Rotate operator backups to prevent disk exhaustion. Disk/volume
snapshots may contain the raw key-bearing config: treat them as sensitive, not sanitized exports.

## Restore verification (fresh directory/VM, no live writes)

1. Keep both primary and Actions disabled. Select a fresh protected directory; preserve the
   original source/backup. Check GPG integrity and decrypt only on a trusted operator host.
   Inspect archive names before extraction; reject absolute/traversal/link/special members.
   Extract only this trusted helper's archive into the fresh directory, not over a running system.
2. Restore `n8n/` to the persistent target and restore nonsecret deployment settings. Restore
   N8N_ENCRYPTION_KEY separately at the external key-file path. Set UID/GID 1000 and 0700 for
   n8n data; key file 0400. Do NOT copy `nonsecret-instance-settings.json` to `.n8n/config`:
   on first CLI start n8n recreates config with the separately supplied key. Restore any needed
   nonsecret settings intentionally after reviewing their compatibility.
3. Select the **same pinned n8n version** as the backup. Before starting its server, run:

```sh
docker compose --env-file /etc/rome-mobility-n8n/deployment.env -f ops/n8n/oci/compose.yaml run --rm --no-deps n8n unpublish:workflow --all
docker compose --env-file /etc/rome-mobility-n8n/deployment.env -f ops/n8n/oci/compose.yaml run --rm --no-deps n8n export:workflow --all --output=/home/node/.n8n/restore-verification.json
```

These are CLI commands, not a running scheduler. Inspect the export privately to verify all
workflows inactive/unpublished; never print/commit it. If unpublish cannot be verified, STOP
before starting the server. Publication semantics are version-dependent; do not substitute
editing a guessed SQLite column. The original database may contain published workflows.

4. For the first server startup, deny outbound FastAPI access at the test boundary. Confirm
   UI login, workflows and credential availability without revealing credentials. Then permit
   only a controlled authenticated GET /health and GET /ready; **no persistence test** in the
   restore drill unless separately authorized. Remove the private verification export.
5. Confirm the recovered source/model/DB state and that the fallback is disabled/no run in
   flight. Only separate approval may publish the primary workflow. Never start restored and
   original schedulers together. Record restore success privately without payloads or keys.

Rollback after a failed version upgrade: stop upgraded n8n, restore the pre-upgrade snapshot
and separate key on the old pinned version, then follow the same unpublished restore drill.

Reference: [n8n CLI unpublish and backup](https://docs.n8n.io/hosting/cli-commands/).
