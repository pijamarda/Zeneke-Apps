# continuous-deployment Specification

## Purpose
Deploys production automatically from GitHub when `main` changes, so that only tested commits reach the server and CI's access to the server is limited to running a deploy.

## Requirements

### Requirement: Pushes to main are deployed automatically
Every push to `main` SHALL start a pipeline that runs the test suite and, when the tests pass, deploys that commit to production with `./deploy.sh` on the server, with no action from a person. A push or pull request that changes only OpenSpec planning files (under `openspec/`) SHALL NOT start the pipeline.

#### Scenario: Passing push
- **WHEN** a commit whose tests pass is pushed to `main`
- **THEN** the pipeline deploys it, production runs that commit, and the pipeline run succeeds

#### Scenario: Planning-only push
- **WHEN** a push to `main` changes only files under `openspec/`, such as archiving a change
- **THEN** no pipeline runs and production is unchanged

#### Scenario: Planning files together with code
- **WHEN** a push to `main` changes files under `openspec/` and any file outside it
- **THEN** the pipeline runs and deploys as for any other push

### Requirement: Failing tests block the deploy
The pipeline SHALL NOT contact the server when the test suite fails. Production SHALL stay on the commit it was running.

#### Scenario: Failing push
- **WHEN** a commit whose tests fail is pushed to `main`
- **THEN** the pipeline run fails at the test step, no deploy is attempted, and production is unchanged

### Requirement: Pull requests are tested but never deployed
The pipeline SHALL run the test suite for pull requests targeting `main` and SHALL NOT deploy from a pull request.

#### Scenario: Pull request opened
- **WHEN** a pull request against `main` is opened or updated
- **THEN** the tests run and report on the pull request, and no deploy is attempted

### Requirement: The deployed commit is the tested commit
A deploy started by the pipeline SHALL put production on exactly the commit whose tests passed in that run, even if newer commits reached `main` in the meantime. It SHALL never move production back to an older commit.

#### Scenario: Newer push during the tests
- **WHEN** commit A is pushed, then commit B is pushed while A's tests are still running, and A's tests pass
- **THEN** A's deploy puts production on A, not on B, and B is only deployed by its own run after B's tests pass

#### Scenario: Stale deploy
- **WHEN** a pipeline run tries to deploy a commit that is older than the one production already runs
- **THEN** production stays on the newer commit and the deploy still checks that the application is healthy

### Requirement: Deploys run one at a time, newest first
Pipeline deploys SHALL never run concurrently. While a deploy is running, at most one deploy SHALL wait, and it SHALL be the most recent one. A running deploy SHALL never be cancelled by a newer push.

#### Scenario: Three quick pushes
- **WHEN** commits A, B and C are pushed in quick succession and all pass their tests while A is deploying
- **THEN** A's deploy finishes, B's deploy is skipped as superseded, and C is deployed next

### Requirement: Manual redeploy
A person SHALL be able to start the pipeline by hand for `main`, which runs the tests and deploys the current head of `main` like a push does.

#### Scenario: Redeploy after fixing the server
- **WHEN** a deploy failed because of a server-side problem, the problem is fixed, and a person starts the pipeline by hand
- **THEN** the tests run and the current head of `main` is deployed

### Requirement: The server is reached only over the private network
The pipeline SHALL reach the server only through the private Tailscale network. The server's SSH port SHALL NOT need to accept connections from GitHub's public IP ranges, and the pipeline's network identity SHALL exist only for the length of a run.

#### Scenario: Public SSH stays filtered
- **WHEN** the pipeline deploys while the server's public SSH access is limited to the owner's IP addresses
- **THEN** the deploy succeeds without that filter being changed

### Requirement: CI credentials can only deploy
The SSH key used by the pipeline SHALL only be able to run `./deploy.sh` on the server: no shell, no other command, no terminal and no forwarding. The pipeline SHALL verify the server's host key against a pinned value and SHALL refuse to connect when it does not match.

#### Scenario: Attempt to run another command
- **WHEN** the CI key is used to request any command other than a deploy, such as a shell
- **THEN** the server runs `./deploy.sh` instead (or refuses), and no other command runs

#### Scenario: Unknown host key
- **WHEN** the address the pipeline connects to presents a host key that does not match the pinned one
- **THEN** the pipeline refuses to connect and the run fails without deploying

### Requirement: Failed deploys fail the run
When `./deploy.sh` exits non-zero or cannot be reached, the pipeline run SHALL fail and its log SHALL contain the script's output, including the application's recent logs when it did not become healthy.

#### Scenario: Application does not become healthy
- **WHEN** a pipeline deploy puts the application in a state where it does not become healthy
- **THEN** the run is marked failed and its log shows the `[deploy]` messages and the application's recent logs

#### Scenario: Server unreachable
- **WHEN** the server cannot be reached over the private network
- **THEN** the run fails within a bounded time instead of hanging
