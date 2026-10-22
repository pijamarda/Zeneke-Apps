# Proposal

## Why

Deploying today means SSHing into the VPS and running `./deploy.sh` by hand after every push to `main`. That step is easy to forget, and nothing checks that the tests pass before production is updated. `deploy.sh` was built to run unchanged from CI (see the archived `vps-deployment` design, decision 7), so the remaining work is the pipeline and the access to the VPS. SSH on the VPS is IP-filtered and GitHub-hosted runners have no fixed IPs, but the VPS is already on Tailscale, so CI can reach it over the tailnet without opening SSH to the internet.

## What Changes

- A **GitHub Actions workflow** that, on every push to `main`, runs the Django test suite and, only if it passes, deploys to the VPS. It can also be started by hand from the Actions tab to redeploy. Pull requests run the tests without deploying.
- **Access over Tailscale**: the deploy job joins the tailnet as a short-lived, tagged node and reaches the VPS's SSH server on its tailnet address. The VPS's public SSH filtering stays as it is.
- **A CI-only SSH key that can only deploy**: its `authorized_keys` line on the VPS forces `deploy.sh` and disables a terminal and all forwarding. CI checks the VPS's host key against a pinned value.
- **Deploy exactly the tested commit**: the workflow passes the commit it tested, and `deploy.sh` fast-forwards to that commit instead of to whatever `origin/main` is at that moment. Run by hand with no argument it behaves as today.
- **One deploy at a time**: deploys are queued, and a deploy waiting in the queue is replaced by a newer one.
- **Docs**: `DEPLOY.md` replaces "Later: deploy from GitHub Actions" with the one-time setup (Tailscale OAuth client and ACL, CI key, GitHub secrets) and how to read a failed run.

## Capabilities

### New Capabilities
- `continuous-deployment`: deploying production automatically from GitHub on pushes to `main`, covering the test gate, which commit is deployed, ordering of deploys, how CI is allowed to reach the server, and how failures are reported.

### Modified Capabilities
- `deployment`: the requirement "One-command deploy" gains an optional target commit, so a deploy can be pinned to a specific commit on `main`.

## Impact

- **New file**: `.github/workflows/deploy.yml`.
- **Script**: `deploy.sh` accepts an optional commit, from its first argument or from the SSH forced-command environment, validated strictly before use.
- **Docs**: `DEPLOY.md`.
- **Outside the repo (manual, by you)**: a Tailscale OAuth client and a `tag:ci` ACL rule; a CI key line in `authorized_keys` on the VPS; GitHub repository secrets; making sure the VPS checkout can `git fetch` without a prompt.
- **Out of scope**: building images in CI or using a registry; zero-downtime deploys; automatic rollback when a deploy fails (the app stays on the failed build, as with a manual deploy, and a revert on `main` redeploys); notifications other than GitHub's own failed-run emails.
