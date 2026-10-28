# Proposal

## Why

Kids can only see their Fercoins balance and history today. They can't see which chores earn coins or how many, and they have nothing to spend the coins on inside the app. Every reward also depends on a parent remembering to enter it by hand. Kids should be able to see what they can earn, tell their parents when they've done a chore, and spend their coins on prizes, while parents keep the final say.

## What Changes

- Kids see the **list of active earning chores** (chores worth positive fercoins) with their value on the Fercoins dashboard. Penalty chores (negative values) stay hidden from kids.
- Kids can **claim a chore** ("¡Lo hice!"). The claim waits for a parent to review it. **Approving** it credits the chore's value as a normal Fercoins transaction. **Rejecting** it credits nothing. A kid can have only **one pending claim per chore**.
- Parents manage a **prize catalog** (name, optional description, cost in fercoins, active or inactive), just as they manage chores today.
- Kids **browse active prizes** and **request** one. A pending request **reserves** its cost: the kid's **available** balance (balance minus pending request costs) must cover it, and the dashboard shows both the balance and the available amount. A kid can **cancel** their own pending request.
- **Approving** a prize request deducts the cost, as fixed when the kid made the request, as a normal Fercoins transaction. **Rejecting** or cancelling it releases the reserved coins. Rejections can include an optional reason.
- Parents get a **pending review page** that lists pending chore claims and prize requests, with a pending count on the Fercoins manage page.
- Kids see the status of their recent claims and requests (pending, approved, rejected, cancelled).
- The existing manual "Dar fercoins" flow stays the same.

## Capabilities

### New Capabilities
- `fercoins-chore-claims`: Kids see the chores they can earn coins for, claim them as done, and parents approve or reject the claims.
- `fercoins-prizes`: The prize catalog, kids requesting prizes against their available balance, coin reservation, and parents approving or rejecting requests.

### Modified Capabilities
- `fercoins`: Adds a parent review page that collects all pending kid claims and prize requests, and limits claiming and requesting to kid accounts, consistent with the existing kids-only membership rule.

## Impact

- **Code**: `fercoins` gets new models (`Prize`, `ChoreClaim`, `PrizeRequest`) and a migration, new kid views (claim chore, request prize, cancel request), new parent views (prize CRUD, pending review, approve or reject actions), forms, admin registrations and URLs. `get_balance` gets an "available balance" companion. Templates: the kid dashboard gains chores, prizes and "my requests" sections; there are new templates for prizes and pending review; the manage page shows the pending count. All UI text is in Spanish.
- **Data**: new tables only. Existing chores and transactions don't change. Approved claims and requests create ordinary `FercoinTransaction` rows, so history and balance logic keep working.
- **Dependencies**: none new.
- **Out of scope**: kids suggesting new prizes, per-chore frequency limits (for example, once a day), a "delivered" state for prizes, prize stock limits, and notifications (email or push). Each could be a follow-up change.
