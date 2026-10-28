# Spec Delta

## Purpose

Gives kids something to spend fercoins on: parents keep a catalog of prizes, kids request them with coins they have available, and a parent approves or rejects each request.

## ADDED Requirements

### Requirement: Parent manages the prize catalog
A parent SHALL be able to create and edit prizes with a name, an optional description and a cost, and to mark a prize active or inactive. The cost SHALL be a whole number of at least 1. Only parents SHALL be able to manage prizes.

#### Scenario: Create prize
- **WHEN** a parent creates the prize "Helado" costing 20
- **THEN** "Helado" appears in the prize catalog as active with a cost of 20

#### Scenario: Invalid cost
- **WHEN** a parent saves a prize with a cost of 0 or -5
- **THEN** the prize is not saved and the parent sees an error

#### Scenario: Kid cannot manage prizes
- **WHEN** a signed-in kid requests the prize management pages
- **THEN** access is denied

### Requirement: Kids see their balance and available coins
The kid's dashboard SHALL show the balance and the available coins. The available amount is the balance minus the costs of the kid's pending prize requests.

#### Scenario: Pending request reduces available coins
- **WHEN** `leo` has a balance of 42 and one pending request costing 20
- **THEN** the dashboard shows a balance of 42 and 22 available

#### Scenario: No pending requests
- **WHEN** `leo` has a balance of 42 and no pending requests
- **THEN** the available amount equals the balance

### Requirement: Kids see the active prizes
The kid's dashboard SHALL list every active prize with its name, description and cost. A prize whose cost is higher than the kid's available coins SHALL show how many more fercoins are needed, and SHALL NOT offer the request action. Inactive prizes SHALL NOT be listed.

#### Scenario: Affordable and unaffordable prizes
- **WHEN** `leo` has 22 available and the active prizes are "Helado" (20) and "Cine" (80)
- **THEN** "Helado" can be requested, and "Cine" shows that 58 more fercoins are needed

#### Scenario: Inactive prize hidden
- **WHEN** a parent marks "Cine" inactive
- **THEN** kids no longer see "Cine"

### Requirement: Kid requests a prize
A kid SHALL be able to request an active prize whose cost does not exceed their available coins. A request SHALL be created as pending and SHALL record the prize's cost at the time of the request. Requesting SHALL NOT change the balance, but SHALL reduce the available coins by the recorded cost.

#### Scenario: Request created
- **WHEN** `leo` with a balance of 42 and 42 available requests "Helado" (20)
- **THEN** a pending request for 20 exists, the balance is still 42, and 22 are available

#### Scenario: Cost fixed at request time
- **WHEN** a parent raises the cost of "Helado" from 20 to 25 while `leo`'s request is pending, and then approves it
- **THEN** 20 fercoins are deducted

### Requirement: Requests cannot exceed available coins
The system SHALL reject a prize request when the prize's cost exceeds the kid's available coins at the moment of the request, or when the prize does not exist or is inactive, even when the request is forged.

#### Scenario: Not enough available coins
- **WHEN** `leo` has 30 available, requests "Helado" (20), and then requests "Helado" again
- **THEN** the second request is rejected because only 10 remain available

#### Scenario: Forged request for an inactive prize
- **WHEN** a kid submits a request with the id of an inactive prize
- **THEN** no request is created

### Requirement: Kid cancels a pending request
A kid SHALL be able to cancel their own pending prize request. Cancelling SHALL mark the request cancelled and release its reserved coins. A kid SHALL NOT be able to cancel another kid's request or a request that is no longer pending.

#### Scenario: Cancel
- **WHEN** `leo` cancels the pending "Helado" request (20) with a balance of 42
- **THEN** the request is cancelled and 42 are available again

#### Scenario: Cancel someone else's request
- **WHEN** `leo` submits a cancellation for one of `ana`'s pending requests
- **THEN** `ana`'s request stays pending

### Requirement: Parent approves a prize request
A parent SHALL be able to approve a pending prize request. Approval SHALL deduct the request's recorded cost as a Fercoins transaction that names the prize and the approving parent, and SHALL mark the request approved. Approval SHALL succeed even if the kid's balance has dropped below the cost since the request, for example after a penalty, in which case the balance may become negative.

#### Scenario: Approve
- **WHEN** a parent approves `leo`'s pending "Helado" request (20) and `leo` has a balance of 42
- **THEN** the balance becomes 22, the history shows the "Helado" prize -20, and the request is approved

#### Scenario: Prize deactivated meanwhile
- **WHEN** a parent deactivates "Helado" while `leo`'s request is pending and then approves the request
- **THEN** the recorded cost is deducted

### Requirement: Parent rejects a prize request
A parent SHALL be able to reject a pending prize request, optionally giving a short reason. Rejection SHALL NOT change the balance and SHALL release the reserved coins.

#### Scenario: Reject
- **WHEN** a parent rejects `leo`'s pending "Helado" request (20) with the reason "Hoy no, mañana"
- **THEN** the balance is unchanged, the available coins rise by 20, and `leo` can see the reason

### Requirement: Only pending requests can be reviewed
Approving, rejecting or cancelling a prize request that is no longer pending SHALL have no effect. In particular, a request SHALL never deduct coins more than once.

#### Scenario: Double approval
- **WHEN** a parent submits the approval for the same request twice
- **THEN** the cost is deducted only once

#### Scenario: Kid cancels after approval
- **WHEN** `leo` tries to cancel a request that a parent has already approved
- **THEN** the request stays approved and the deduction remains

### Requirement: Kid sees the status of their requests
The kid's dashboard SHALL show the kid's recent prize requests with their status (pending, approved, rejected or cancelled) and, for rejected requests, any reason given. A kid SHALL NOT see other kids' requests.

#### Scenario: Own requests only
- **WHEN** `leo` and `ana` each have prize requests and `leo` opens the dashboard
- **THEN** only `leo`'s requests are shown
