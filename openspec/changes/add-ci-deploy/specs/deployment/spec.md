# Spec Delta

## MODIFIED Requirements

### Requirement: One-command deploy
Running `./deploy.sh` on the server SHALL update the code to the latest `origin/main`, back up the database, rebuild and start the application, and wait until it reports healthy. It SHALL then print the deployed commit and exit with status 0. It SHALL need no interactive input. When given a full commit hash that is on `origin/main`, it SHALL update the code to that commit instead of the latest one; it SHALL never move the checkout back to an older commit.

#### Scenario: New commit on main
- **WHEN** a new commit was pushed to `main` and an operator runs `./deploy.sh`
- **THEN** the server runs that commit, the application is healthy, and the script prints the commit and exits 0

#### Scenario: Nothing new
- **WHEN** `./deploy.sh` runs and `main` has no new commits
- **THEN** the script still ensures the application is up and healthy and exits 0

#### Scenario: Pinned to a commit
- **WHEN** `origin/main` has commits A then B, the server runs an older commit, and `./deploy.sh` is given A's full hash
- **THEN** the server runs A, not B, and the script prints A and exits 0

#### Scenario: Pinned commit already deployed or older
- **WHEN** `./deploy.sh` is given the hash of a commit on `main` that is the one the server runs or older than it
- **THEN** the checkout does not change, the application is ensured up and healthy, and the script exits 0

#### Scenario: Invalid target
- **WHEN** `./deploy.sh` is given something that is not a full commit hash, or a hash that is not on `origin/main`
- **THEN** it exits non-zero with a clear message before backing up or rebuilding anything
