# Spec Delta

## Purpose

Defines the home page as the entry point to the family apps: which app cards each kind of visitor sees and how the page greets them.

## ADDED Requirements

### Requirement: App cards on the home page
The home page SHALL show a card for each app the visitor can open: Bingo and Fercoins for everyone. Each card SHALL link to that app.

#### Scenario: Signed-out visitor
- **WHEN** an anonymous visitor opens the home page
- **THEN** it shows a Bingo card linking to the Bingo start page and a Fercoins card linking to the Fercoins dashboard

#### Scenario: Signed-in kid
- **WHEN** a signed-in kid opens the home page
- **THEN** it shows the Bingo and Fercoins cards

### Requirement: Fercoins card says when sign-in is needed
For an anonymous visitor, the Fercoins card SHALL say that a sign-in is needed. For a signed-in user, it SHALL NOT say so.

#### Scenario: Anonymous visitor sees the sign-in note
- **WHEN** an anonymous visitor opens the home page
- **THEN** the Fercoins card states that it needs a sign-in

#### Scenario: Signed-in user sees no sign-in note
- **WHEN** a signed-in kid opens the home page
- **THEN** the Fercoins card has no sign-in note

### Requirement: Family card only for parents
The home page SHALL show a Familia card linking to family management only to parents (superusers). Kids, other accounts and anonymous visitors SHALL NOT see it.

#### Scenario: Parent sees the Familia card
- **WHEN** a parent opens the home page
- **THEN** it shows a Familia card linking to the family management page

#### Scenario: Kid does not see the Familia card
- **WHEN** a signed-in kid or an anonymous visitor opens the home page
- **THEN** no Familia card or link to family management appears in the page content

### Requirement: Greeting for signed-in users
When the visitor is signed in, the home page SHALL greet them by their username. Anonymous visitors SHALL see a general welcome instead.

#### Scenario: Kid is greeted by name
- **WHEN** kid `leo` opens the home page
- **THEN** the page greets `leo` by name

#### Scenario: Anonymous visitor
- **WHEN** an anonymous visitor opens the home page
- **THEN** the page shows a general welcome without any username
