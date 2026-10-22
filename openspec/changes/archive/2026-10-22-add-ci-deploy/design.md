# Design

## Context

See proposal.md for the why. Relevant current state:

- `deploy.sh` runs on the VPS from the repo checkout. It is non-interactive, takes a `flock`, refuses unsafe states, fetches and fast-forwards `main` to `origin/main`, backs up, rebuilds with `docker compose up --build --wait`, and exits non-zero with the app's logs when it isn't healthy.
- The archived `vps-deployment` design (decision 7) already chose SSH with a dedicated key whose `authorized_keys` line forces `deploy.sh`.
- The VPS's public SSH is IP-filtered, and the VPS is already on the owner's Tailscale tailnet.
- Tests: `uv run --project .. python manage.py test` from `src/app`, about 155 tests in about 2.5 minutes. They need `DEBUG=true` and `ALLOWED_HOSTS` including `localhost`.
- There is no `.github/` directory yet.

## Goals / Non-Goals

**Goals:**
- One workflow file, no new services, and no change to how the VPS builds and runs the app.
- A leaked GitHub secret should not give anyone a shell on the VPS.

**Non-Goals:**
- Building or pushing images from CI. The VPS keeps building from its checkout.
- Changing the VPS's public firewall.
- Rolling back automatically on a failed deploy.

## Decisions

### 1. Reach the VPS over Tailscale with an ephemeral, tagged node
The deploy job uses the official `tailscale/github-action` with a Tailscale **OAuth client** limited to creating `tag:ci` devices. Each run joins as an ephemeral node, which Tailscale removes after the job.
- OAuth clients don't expire, unlike auth keys (90 days at most), so the pipeline doesn't break silently every quarter.
- The tailnet policy gets an explicit rule that lets `tag:ci` reach **only the VPS on TCP 22**. If the tailnet still uses the default allow-all policy, this rule and a restriction for `tag:ci` have to be added, otherwise a CI node could reach every device on the tailnet.
- *Alternatives:* allowlisting GitHub's published runner ranges (thousands of Azure CIDRs that change weekly, which is close to opening SSH to all of Azure); a self-hosted runner on the VPS (no inbound SSH at all, but GitHub advises against self-hosted runners on public repos, and workflow code would run on the production box); opening the Oracle security list per run with the OCI CLI (CI would then hold cloud credentials able to change the network). If Tailscale's OIDC workload identity federation is available for the action when this is built, it can replace the OAuth secret with no other change.

### 2. Plain sshd on the tailnet address, not Tailscale SSH
CI runs `ssh` to the VPS's tailnet name or `100.x` address, which reaches the normal OpenSSH server. **Tailscale SSH must not be used for this connection**: it authenticates by tailnet identity and ignores `authorized_keys`, so the forced command would not apply. If Tailscale SSH is enabled on the VPS, the policy's `ssh` section must not grant `tag:ci`.
- Tailscale SSH, when on, owns port 22 on the tailnet address (found on the first real run). The owner keeps it for their own logins, so sshd also listens on port 2222, reachable only over the tailnet. The workflow takes the port from the `DEPLOY_PORT` environment variable (default 22), and the host key is scanned on that port.

### 3. The CI key is forced to `deploy.sh`
On the VPS, the CI public key is added to the `authorized_keys` of the user who owns the checkout:
```
command="/home/<user>/zeneke-apps/deploy.sh --ssh",from="100.64.0.0/10,fd7a:115c:a1e0::/48",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty,no-user-rc ssh-ed25519 AAAA... zeneke-ci
```
The `from=` part limits the key to tailnet addresses (Tailscale's IPv4 and IPv6 ranges). Whatever the client asks to run, sshd runs `deploy.sh` and puts the requested command line in `SSH_ORIGINAL_COMMAND`.
- CI pins the VPS host key: `known_hosts` comes from a secret, with `StrictHostKeyChecking=yes`. The value is collected once on the VPS with `ssh-keyscan` against its own tailnet name, and is checked against the server's fingerprint.
- A dedicated `deploy` user isn't worth it here: it would need Docker access, which is root-equivalent anyway, plus ownership of the checkout. The forced command is the real boundary.

### 4. Deploy exactly the tested commit
`deploy.sh` reads an optional target from `$1`. Under the forced command it is started as `deploy.sh --ssh`, and then reads the target from `SSH_ORIGINAL_COMMAND`. CI runs `ssh <host> "$GITHUB_SHA"`, which sshd hands over as `SSH_ORIGINAL_COMMAND`.
- The explicit `--ssh` matters. sshd sets `SSH_ORIGINAL_COMMAND` for every key, so reading it unconditionally would break `ssh vps ./deploy.sh` run with the owner's normal key (the target would become `./deploy.sh`).
- **Validation (preflight, before anything changes):** the target must match `^[0-9a-f]{40}$`. Anything else, such as `bash` or a path, fails with a message. That keeps the forced command from being turned into anything other than a deploy.
- **After `git fetch origin main`:** the target must be an ancestor of, or equal to, `origin/main` (`git merge-base --is-ancestor`), otherwise the script fails. If the target is already contained in `HEAD`, the checkout is left alone. Otherwise the script runs `git merge --ff-only <target>`.
- With no target, the behaviour is the same as today (`origin/main`), so manual runs are unchanged.
- *Alternative:* the deploy job checks that `GITHUB_SHA` is still the head of `main` and skips otherwise. Rejected: a race remains between the check and the server's fetch, and a commit could be deployed before its own tests finish.

### 5. Workflow shape
`.github/workflows/deploy.yml`, with triggers `push` to `main`, `pull_request` to `main`, and `workflow_dispatch`. Top-level `permissions: contents: read`.
- **`test` job** (every trigger): checkout, `astral-sh/setup-uv` (Python from `pyproject.toml`), `uv sync --locked` in `src/`, then the test command in `src/app` with `DEBUG=true`, `ALLOWED_HOSTS=localhost,127.0.0.1` and a throwaway `SECRET_KEY` as job env, so no `.env` file is needed.
- **`deploy` job**: `needs: test`, `if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'`, `environment: production`, `timeout-minutes: 15`, and
  `concurrency: { group: production-deploy, cancel-in-progress: false }`. GitHub's concurrency already gives the spec's ordering: a running deploy is never cancelled, and only the newest pending deploy is kept.
  Steps: Tailscale up (tags `tag:ci`), write the key and `known_hosts` into `~/.ssh` with mode 600, then `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 "$DEPLOY_USER@$DEPLOY_HOST" "$GITHUB_SHA"`. The script's output streams into the job log, and its exit status becomes the step's status.
- Third-party actions are pinned to full commit SHAs, with a version comment.
- The test job has no concurrency group, so tests for several pushes can run in parallel.

### 6. Secrets live in a `production` environment
These are GitHub **environment** secrets on an environment called `production`, with a deployment-branch rule that allows only `main`: `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`, `DEPLOY_HOST`, `DEPLOY_USER`. Pull-request runs can't read them, even from a branch in the repo. The environment can later gain a required reviewer if a manual approval step is ever wanted.

### 7. The VPS fetch must work unattended
`deploy.sh` runs `git fetch` under the forced command, with no agent and no terminal. The checkout's `origin` must work non-interactively: the public HTTPS URL, or a read-only deploy key without a passphrase if the repo ever becomes private. `DEPLOY.md` says how to check this.

## Risks / Trade-offs

- [A manual `./deploy.sh` and a CI deploy overlap] → `deploy.sh`'s lock makes the second fail with "another deploy is already running". If CI was the one refused, rerun it from the Actions tab.
- [Tailscale or GitHub outage] → the run fails within the timeouts. Deploying by hand over SSH still works.
- [Leaked `DEPLOY_SSH_KEY`] → it only runs `deploy.sh`, can only deploy commits already on `main`, and is only usable from the tailnet (with `from=`). Revoke it by removing the line.
- [Leaked Tailscale OAuth secret] → the attacker can join as `tag:ci`, which the policy limits to TCP 22 on the VPS, where they still need the SSH key. Revoke the client in the Tailscale admin console.
- [A deploy that fails leaves the app down] → the same as a manual deploy today. The run fails and GitHub emails the pusher. Fix forward, or revert on `main`, which redeploys.
- [A broken test suite blocks all deploys] → intended. In an emergency, `./deploy.sh` by hand still works.
- [The VPS builds on every push] → about a minute of CPU per deploy, already accepted in `vps-deployment`.

## Migration Plan

1. Merge this change. The workflow runs tests on the PR itself, but can't deploy until the secrets exist, so the first push to `main` would fail at the Tailscale step. Do the one-time setup (tasks section 1) **before merging**.
2. The merge push deploys the merge commit. Check the run log and `https://apps.zeneke.com/healthz`.
3. **Rollback of the pipeline itself:** disable the workflow in the Actions tab, or remove the CI line from `authorized_keys`. Manual deploys are unaffected.
