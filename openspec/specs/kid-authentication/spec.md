# kid-authentication Specification

## Purpose

Lets kid accounts sign in with a username and a 4-digit PIN they choose themselves. The login is protected against guessing, because the site is exposed to the internet.

## Requirements

### Requirement: Kid sign-in form on the login page
The login page SHALL offer a kid sign-in form (username, and a code field that accepts either a 4-digit PIN or a 6-digit setup code) alongside the existing Google and GitHub sign-in options. It SHALL NOT list or reveal the names of any accounts.

#### Scenario: Login page shows both options
- **WHEN** an anonymous visitor opens the login page
- **THEN** the page shows the Google and GitHub sign-in buttons and a username + PIN form
- **AND** no account usernames appear on the page

### Requirement: PIN format
A PIN SHALL be exactly 4 digits (0-9). Any other value SHALL be rejected when a PIN is chosen or changed.

#### Scenario: Valid PIN accepted
- **WHEN** a kid chooses the PIN `0427`
- **THEN** the PIN is accepted

#### Scenario: Invalid PIN rejected
- **WHEN** a kid chooses `123`, `12345` or `12a4`
- **THEN** the system rejects it with a message that the PIN must be 4 digits

### Requirement: Kid signs in with username and PIN
The system SHALL sign in a kid account when the submitted username matches a kid account, ignoring letter case, and the submitted PIN matches that account's PIN. After signing in, the kid SHALL land on the Fercoins dashboard.

#### Scenario: Correct credentials
- **WHEN** a kid submits their username and correct PIN
- **THEN** the kid is signed in and redirected to the Fercoins dashboard

#### Scenario: Username letter case is ignored
- **WHEN** kid `leo` submits the username `Leo` with the correct PIN
- **THEN** the kid is signed in

#### Scenario: Next URL is honoured
- **WHEN** a kid was sent to the login page from a protected page and then signs in successfully
- **THEN** the kid is redirected back to that page if it is on this site

### Requirement: Only kid accounts can use PIN sign-in
PIN and setup-code sign-in SHALL succeed only for accounts with the kid role. It SHALL NOT sign in parent (superuser) accounts or any other non-kid account, whatever value is submitted.

#### Scenario: Parent username via PIN form
- **WHEN** someone submits a parent's username and any PIN in the kid form
- **THEN** sign-in fails with the generic failure message

### Requirement: Generic failure message
Every failed PIN sign-in SHALL show the same message, whatever the cause: unknown username, non-kid account, wrong PIN, or locked account. The response SHALL NOT reveal which of these happened.

#### Scenario: Unknown username and wrong PIN look the same
- **WHEN** one attempt uses a username that does not exist and another uses a real kid username with a wrong PIN
- **THEN** both responses show the identical failure message

### Requirement: Lockout after repeated failures
After 5 consecutive failed PIN attempts on a kid account, that account SHALL be locked for 15 minutes. While it is locked, sign-in SHALL fail even with the correct PIN. A successful sign-in SHALL reset the failure count. The count SHALL be shared across all server processes.

#### Scenario: Fifth failure locks the account
- **WHEN** a kid account receives 5 consecutive wrong PINs
- **THEN** a 6th attempt with the correct PIN fails with the generic failure message

#### Scenario: Lock expires
- **WHEN** 15 minutes have passed since the account was locked
- **THEN** sign-in with the correct PIN succeeds

#### Scenario: Success resets the count
- **WHEN** a kid enters 4 wrong PINs, then the correct PIN, then 4 more wrong PINs
- **THEN** the account is not locked

### Requirement: Kid chooses PIN using a one-time setup code
A kid account awaiting setup SHALL be signed in through the kid form using its username and its valid one-time setup code in place of a PIN. The kid SHALL then choose a PIN, entered twice, before reaching any other page. Choosing the PIN completes sign-in and invalidates the setup code. Failed setup-code attempts SHALL count toward the lockout.

#### Scenario: First sign-in with setup code
- **WHEN** a kid awaiting setup submits their username and their valid setup code
- **THEN** the kid is shown a "choose your PIN" page
- **AND** after entering the same valid PIN twice, the kid is signed in and lands on the Fercoins dashboard

#### Scenario: Username alone is not enough
- **WHEN** someone submits the username of a kid awaiting setup with a wrong or empty code
- **THEN** sign-in fails with the generic failure message

#### Scenario: Expired setup code
- **WHEN** a kid submits a setup code more than 24 hours after it was issued
- **THEN** sign-in fails with the generic failure message

#### Scenario: Setup code is single use
- **WHEN** a kid has chosen a PIN and someone later submits the old setup code
- **THEN** sign-in fails with the generic failure message

#### Scenario: Mismatched confirmation
- **WHEN** the two PIN entries differ
- **THEN** the PIN is not saved and the kid is asked to try again

#### Scenario: Cannot skip choosing a PIN
- **WHEN** a kid in the "choose your PIN" step navigates to any other page
- **THEN** the kid is not signed in and is returned to the "choose your PIN" page or the login page

### Requirement: Kid changes own PIN
A signed-in kid SHALL be able to change their PIN by entering their current PIN and the new PIN twice. A wrong current PIN SHALL count as a failed attempt for the lockout.

#### Scenario: Successful change
- **WHEN** a signed-in kid enters the correct current PIN and a valid new PIN twice
- **THEN** the new PIN is saved, the kid stays signed in, and the old PIN no longer works

#### Scenario: Wrong current PIN
- **WHEN** a signed-in kid enters an incorrect current PIN
- **THEN** the PIN is not changed and the failure counts toward the lockout

### Requirement: PINs are never stored or shown in plain text
PINs and setup codes SHALL be stored only as salted one-way hashes. A PIN SHALL never be displayed to anyone after entry, including parents.

#### Scenario: Stored value is hashed
- **WHEN** a kid chooses a PIN
- **THEN** the stored credential does not contain the PIN digits in plain text

### Requirement: Kid session duration
A kid's sign-in SHALL stay valid for 2 weeks, or until the kid logs out.

#### Scenario: Session persists across browser restarts
- **WHEN** a kid signs in and reopens the browser within 2 weeks
- **THEN** the kid is still signed in
