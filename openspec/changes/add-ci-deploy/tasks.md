## 1. One-time setup outside the repo (manual, before merging)

- [ ] 1.1 Tailscale policy: add `tag:ci` to `tagOwners`, and a grant/ACL rule allowing `tag:ci` to reach only the VPS on `tcp:22`. Make sure no broader rule (such as default allow-all) covers `tag:ci`, and that no Tailscale SSH rule grants `tag:ci`.
- [ ] 1.2 Tailscale admin console: create an OAuth client with the `auth_keys` write scope, limited to `tag:ci`. Keep its ID and secret for 1.6.
- [ ] 1.3 On the dev machine, create the CI key without a passphrase: `ssh-keygen -t ed25519 -N "" -C zeneke-ci -f zeneke-ci`
- [ ] 1.4 On the VPS, append the restricted line from design decision 3 (`DEPLOY.md`, "Automatic deploys", step 4) (with the real checkout path and `zeneke-ci.pub`) to `~/.ssh/authorized_keys` of the checkout owner.
- [ ] 1.5 On the VPS, collect the host key for its tailnet IP: `ssh-keyscan -t ed25519 <tailnet-ip>`. Compare its fingerprint with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.
- [ ] 1.6 GitHub: create the `production` environment, restricted to the `main` branch, with secrets `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`, `DEPLOY_SSH_KEY` (contents of `zeneke-ci`), `DEPLOY_KNOWN_HOSTS` (output of 1.5), `DEPLOY_HOST` (the same tailnet IP) and `DEPLOY_USER`. Then delete the local private key file.
- [ ] 1.7 On the VPS, in the checkout, confirm the fetch is unattended: `git remote -v` shows an HTTPS URL (or a passphrase-less deploy key), and `env -u SSH_AUTH_SOCK git fetch origin main` succeeds without a prompt.

## 2. Pin deploy.sh to a commit

- [x] 2.1 Read the target from `$1`, or from `SSH_ORIGINAL_COMMAND` when started as `deploy.sh --ssh`. When non-empty, reject anything not matching `^[0-9a-f]{40}$` in preflight, with a clear `[deploy] ERROR`.
- [x] 2.2 After `git fetch`, fail when the target is not an ancestor of, or equal to, `origin/main`. Leave the checkout alone when `HEAD` already contains the target. Otherwise run `git merge --ff-only <target>`. With no target, keep today's fast-forward to `origin/main`.
- [x] 2.3 Update the header comment and `DEPLOY.md`'s operations table to mention the optional commit.
- [x] 2.4 Test against a scratch clone with a local bare `origin` and a spare port, as in `vps-deployment`: no target; target = older commit on main (pins to it); target already deployed; target older than `HEAD` (no change, exit 0); a non-hash such as `bash` (refused before backup); a hash not on `origin/main` (refused before backup); a valid hash and `bash` given through `SSH_ORIGINAL_COMMAND` with `--ssh` (pins, and refuses, respectively); `SSH_ORIGINAL_COMMAND` set without `--ssh` (ignored). Docker is stubbed for the git-logic cases; the build, wait and failure paths are unchanged from `vps-deployment`.

## 3. Workflow

- [x] 3.1 Add `.github/workflows/deploy.yml` with the triggers, permissions, `test` job and `deploy` job from design decision 5, with actions pinned to commit SHAs.
- [x] 3.2 Open the PR and check that the `test` job runs and passes on it, and that `deploy` is skipped.

## 4. Docs

- [x] 4.1 Replace "Later: deploy from GitHub Actions" in `DEPLOY.md` with "Automatic deploys": what triggers a deploy, the one-time setup from section 1 (fish-compatible commands), how to rerun or start a deploy from the Actions tab, how to read a failed run, and how to switch the pipeline off.
- [x] 4.2 Note in `DEPLOY.md`'s troubleshooting that "another deploy is already running" in CI means a manual deploy overlapped, and the run can be rerun.

## 5. First automatic deploy

- [ ] 5.1 After merging, watch the run triggered by the merge: tests pass, the deploy log ends with `[deploy] deployed <sha>` matching the merge commit, and `https://apps.zeneke.com/healthz` answers `ok`.
