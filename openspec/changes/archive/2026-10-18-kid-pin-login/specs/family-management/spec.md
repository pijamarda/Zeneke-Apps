# Spec Delta

## Purpose

Lets parents manage the family's kid accounts in one place: creating them, handing out setup codes, resetting PINs and unlocking accounts. Other family apps can then rely on a single definition of who the kids are.

## ADDED Requirements

### Requirement: Family page is parent-only
The family management page and its actions SHALL be available only to parents (superusers). Anyone else SHALL be denied access.

#### Scenario: Kid tries to open the family page
- **WHEN** a signed-in kid requests the family management page
- **THEN** access is denied and no kid data is shown

#### Scenario: Anonymous visitor
- **WHEN** an anonymous visitor requests the family management page
- **THEN** the visitor is redirected to the login page

### Requirement: Family page lists kids and their state
The family management page SHALL list every kid account with its username and state: awaiting setup, active, or locked (including when the lock ends).

#### Scenario: Mixed states
- **WHEN** a parent opens the family page with one kid awaiting setup, one active and one locked
- **THEN** each kid is shown with the matching state

### Requirement: Parent creates a kid account
A parent SHALL be able to create a kid account by entering a username, which must be unique across all accounts, ignoring letter case. The new account SHALL have the kid role, no PIN, and no ability to sign in through Google or GitHub or the admin site.

#### Scenario: Create kid
- **WHEN** a parent creates a kid with username `leo_rocket`
- **THEN** a kid account `leo_rocket` exists in the "awaiting setup" state

#### Scenario: Duplicate username
- **WHEN** a parent creates a kid with a username that already exists, including one that differs only in letter case (`Leo` vs `leo`)
- **THEN** no account is created and the parent sees an error

### Requirement: Setup code is shown once to the parent
Creating a kid or resetting a kid's PIN SHALL issue a new random 6-digit setup code, valid for 24 hours, and show it to the parent exactly once. Issuing a new code SHALL invalidate any previous code for that kid. The page showing the code SHALL instruct the browser not to cache it.

#### Scenario: Code shown after creation
- **WHEN** a parent creates a kid
- **THEN** the parent sees the kid's 6-digit setup code and that it expires in 24 hours

#### Scenario: Code not shown again
- **WHEN** the parent reloads or returns to the family page later
- **THEN** the setup code is not displayed again

#### Scenario: Back button does not reveal the code
- **WHEN** the parent navigates away from the code page and presses the browser's back button
- **THEN** the browser does not show the code from its cache

#### Scenario: New code replaces old
- **WHEN** a parent issues a second setup code for the same kid
- **THEN** the first code no longer works

### Requirement: Parent resets a kid's PIN
A parent SHALL be able to reset a kid's PIN. A reset SHALL remove the current PIN, clear any lock and failure count, put the account into "awaiting setup", issue a new setup code, and sign the kid out of all existing sessions.

#### Scenario: Forgotten PIN
- **WHEN** a parent resets the PIN of an active kid
- **THEN** the old PIN no longer works, the parent sees a new setup code, and the kid can sign in with that code to choose a new PIN

#### Scenario: Reset of a locked kid
- **WHEN** a parent resets the PIN of a locked kid
- **THEN** the kid can immediately sign in with the new setup code

#### Scenario: Existing sessions end
- **WHEN** a parent resets the PIN of a kid who is signed in on a tablet
- **THEN** the kid's next request on that tablet is no longer signed in

### Requirement: Parent unlocks a kid account
A parent SHALL be able to unlock a locked kid account. Unlocking SHALL clear the lock and the failure count without changing the PIN.

#### Scenario: Unlock
- **WHEN** a parent unlocks a kid account locked after 5 failures
- **THEN** the kid can immediately sign in with their existing PIN
