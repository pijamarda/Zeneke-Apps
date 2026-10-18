# fercoins Specification

## Purpose

Defines who takes part in Fercoins, the family points app where parents reward or deduct coins for chores and kids see their balance.

## Requirements

### Requirement: Only kid accounts are Fercoins members
The Fercoins member list and the recipient choices on the give form SHALL include only accounts with the kid role. Parents and other non-kid accounts SHALL NOT appear there and SHALL NOT be accepted as recipients.

#### Scenario: OAuth stranger is not a member
- **WHEN** a non-kid, non-superuser account exists (for example, created by someone signing in with Google)
- **THEN** that account does not appear on the Fercoins manage page or in the give form

#### Scenario: Forged recipient rejected
- **WHEN** a parent submits the give form with the id of a non-kid account as the recipient
- **THEN** the form is rejected and no transaction is created

#### Scenario: Kid appears as member
- **WHEN** a parent creates a kid account
- **THEN** the kid appears on the Fercoins manage page with a balance of 0

### Requirement: Empty member list points to family management
When there are no kid accounts, the Fercoins manage page SHALL tell the parent to create kids from the family management page and link to it.

#### Scenario: No kids yet
- **WHEN** a parent opens the Fercoins manage page and no kid accounts exist
- **THEN** the page shows a message with a link to the family management page
