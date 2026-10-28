# Spec Delta

## Purpose

Lets kids see which chores earn fercoins and how many, and tell their parents when they have done one. A parent approves or rejects each claim before any coins are credited.

## ADDED Requirements

### Requirement: Kids see the earning chores
The kid's Fercoins dashboard SHALL list every active chore with a positive fercoins value, showing its name, description and value. Inactive chores and chores with a zero or negative value SHALL NOT be listed for kids.

#### Scenario: Earning chores listed
- **WHEN** active chores "Hacer la cama" (+5) and "Poner la mesa" (+3) exist and a kid opens the dashboard
- **THEN** both chores appear with their values

#### Scenario: Penalties and inactive chores hidden
- **WHEN** an active chore "Pelear" (-5) and an inactive chore "Regar" (+2) exist and a kid opens the dashboard
- **THEN** neither chore appears in the kid's chore list

### Requirement: Kid claims a chore as done
A kid SHALL be able to claim an earning chore from the dashboard. A claim SHALL be created as pending and SHALL record the chore's value at the time of the claim. Claiming SHALL NOT change the kid's balance.

#### Scenario: Claim created
- **WHEN** kid `leo` with a balance of 10 claims "Hacer la cama" (+5)
- **THEN** a pending claim for 5 fercoins exists for `leo`, `leo`'s balance is still 10, and the chore shows as pending on the dashboard

#### Scenario: Value fixed at claim time
- **WHEN** a parent changes "Hacer la cama" from +5 to +8 while `leo`'s claim is pending, and then approves it
- **THEN** `leo` is credited 5 fercoins

### Requirement: One pending claim per chore per kid
A kid SHALL NOT have more than one pending claim for the same chore. Once that claim has been approved or rejected, the kid SHALL be able to claim the chore again. Different kids SHALL be able to have pending claims for the same chore at the same time.

#### Scenario: Duplicate claim refused
- **WHEN** `leo` has a pending claim for "Hacer la cama" and submits another claim for it
- **THEN** no second claim is created and the chore still shows as pending

#### Scenario: Claim again after review
- **WHEN** a parent approves `leo`'s claim for "Hacer la cama"
- **THEN** `leo` can claim "Hacer la cama" again

#### Scenario: Two kids, same chore
- **WHEN** `leo` has a pending claim for "Poner la mesa" and `ana` claims it too
- **THEN** both claims are pending

### Requirement: Only valid chores can be claimed
The system SHALL reject a claim for a chore that does not exist, is inactive, or has a zero or negative value, even when the request is forged.

#### Scenario: Forged claim on a penalty chore
- **WHEN** a kid submits a claim with the id of the "Pelear" (-5) chore
- **THEN** no claim is created

#### Scenario: Forged claim on an inactive chore
- **WHEN** a kid submits a claim with the id of an inactive chore
- **THEN** no claim is created

### Requirement: Parent approves a chore claim
A parent SHALL be able to approve a pending chore claim. Approval SHALL credit the kid with the claim's recorded value as a Fercoins transaction that names the chore and the approving parent, and SHALL mark the claim approved. Approval SHALL still be possible if the chore has been deactivated since the claim was made.

#### Scenario: Approve
- **WHEN** a parent approves `leo`'s pending claim for "Hacer la cama" (+5)
- **THEN** `leo`'s balance increases by 5, the history shows "Hacer la cama" +5, and the claim is approved

#### Scenario: Chore deactivated meanwhile
- **WHEN** a parent deactivates "Hacer la cama" while `leo`'s claim is pending and then approves the claim
- **THEN** `leo` is credited the recorded value

### Requirement: Parent rejects a chore claim
A parent SHALL be able to reject a pending chore claim, optionally giving a short reason. Rejection SHALL NOT change the kid's balance.

#### Scenario: Reject with reason
- **WHEN** a parent rejects `leo`'s claim for "Hacer la cama" with the reason "La cama sigue deshecha"
- **THEN** `leo`'s balance does not change, the claim is rejected, and `leo` can see the reason

### Requirement: Only pending claims can be reviewed
Approving or rejecting a claim that is no longer pending SHALL have no effect. In particular, a claim SHALL never credit coins more than once.

#### Scenario: Double approval
- **WHEN** a parent submits the approval for the same claim twice (for example, by double-clicking)
- **THEN** the kid is credited only once

#### Scenario: Reject after approval
- **WHEN** a parent tries to reject a claim that is already approved
- **THEN** the claim stays approved and the credited coins remain

### Requirement: Kid sees the status of their claims
The kid's dashboard SHALL show the kid's recent chore claims with their status (pending, approved or rejected) and, for rejected claims, any reason given. A kid SHALL NOT see other kids' claims.

#### Scenario: Own claims only
- **WHEN** `leo` and `ana` each have claims and `leo` opens the dashboard
- **THEN** only `leo`'s claims are shown
