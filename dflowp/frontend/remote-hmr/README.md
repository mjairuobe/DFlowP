# Remote Vite HMR Prep (Frontend only)

This folder prepares `dflowp/frontend` for usage with a long-running remote Vite HMR server,
similar to the `vite-cicd-hmrdevserver` reference approach.

It is additive only: no existing frontend files are modified.

## Files

- `.env.remote-hmr.example`: base configuration for SSH forwarding and supervisor sync.
- `scripts/open-ssh-tunnel.sh`: opens local SSH tunnel for Vite + supervisor ports.
- `scripts/trigger-sync.sh`: triggers `/sync` and waits for terminal state (`READY` etc.).

## Prerequisites

- A remote host already running the long-lived Vite/supervisor setup.
- `ssh`, `curl`, `jq`, `awk` available on your machine (and Jenkins agent for CI use).

## 1) Create local config

```bash
cd dflowp/frontend
cp remote-hmr/.env.remote-hmr.example remote-hmr/.env.remote-hmr.local
```

Then edit `remote-hmr/.env.remote-hmr.local` with your host, ports, and optional secret.

## 2) Open SSH tunnel

```bash
cd dflowp/frontend
bash remote-hmr/scripts/open-ssh-tunnel.sh remote-hmr/.env.remote-hmr.local
```

With defaults, open `http://127.0.0.1:40889` in browser.

## 3) Trigger a sync manually

In a second shell:

```bash
cd dflowp/frontend
bash remote-hmr/scripts/trigger-sync.sh remote-hmr/.env.remote-hmr.local main
```

If no ref is passed, `DFLOWP_REMOTE_HMR_REF` is used.

## 4) Jenkins-triggered sync (example step)

Use this in a Jenkins stage after checkout:

```bash
cd dflowp/frontend
bash remote-hmr/scripts/trigger-sync.sh remote-hmr/.env.remote-hmr.jenkins "${BRANCH_NAME:-main}"
```

Typical Jenkins setup:

- provide `remote-hmr/.env.remote-hmr.jenkins` via managed file or secret mount,
- optionally set `DFLOWP_REMOTE_HMR_SHARED_SECRET` for supervisor auth header,
- fail the stage when script exits non-zero (already handled by shell default).

## Notes

- Keep tunnel targets on `127.0.0.1` to avoid IPv4/IPv6 mismatch issues.
- These files do not replace your existing `refine dev` workflow; they prepare remote-HMR operation.
