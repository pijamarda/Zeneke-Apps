# Spec Delta

## ADDED Requirements

### Requirement: Only kid accounts can claim chores and request prizes
Claiming a chore, requesting a prize and cancelling a request SHALL be available only to kid accounts. Parents and other non-kid accounts SHALL NOT be offered these actions and SHALL be refused if they submit them.

#### Scenario: OAuth stranger tries to claim
- **WHEN** a signed-in non-kid, non-superuser account submits a chore claim or a prize request
- **THEN** the action is refused and no claim or request is created

#### Scenario: Anonymous visitor
- **WHEN** an anonymous visitor submits a chore claim or a prize request
- **THEN** the visitor is redirected to the login page and nothing is created

### Requirement: Parent review page for pending items
The system SHALL provide a parent-only review page that lists every pending chore claim and pending prize request, oldest first. Each entry SHALL show the kid, the chore or prize, the recorded amount and when it was submitted, and SHALL offer approve and reject actions. Approve, reject and cancel SHALL only happen through form submissions, never through links.

#### Scenario: Pending items listed
- **WHEN** `leo` has a pending claim for "Hacer la cama" (+5) and `ana` has a pending request for "Helado" (20)
- **THEN** the review page lists both, each with approve and reject actions

#### Scenario: Kid denied
- **WHEN** a signed-in kid requests the review page
- **THEN** access is denied

#### Scenario: Nothing pending
- **WHEN** there are no pending claims or requests
- **THEN** the review page says there is nothing to review

### Requirement: Manage page shows the pending count
The Fercoins manage page SHALL show the number of pending chore claims and prize requests together, with a link to the review page, whenever that number is above zero.

#### Scenario: Pending items exist
- **WHEN** there are two pending claims and one pending request and a parent opens the manage page
- **THEN** the page shows 3 pending items with a link to the review page

#### Scenario: Nothing pending
- **WHEN** nothing is pending
- **THEN** the manage page shows no pending count
