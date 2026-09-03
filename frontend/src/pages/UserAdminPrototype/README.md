# User Accounts Prototype

A self-contained, **mock-data** prototype of the user account console and the
block request-and-approve flow around it. No backend, no auth, no env vars —
everything renders from [`mockData.js`](./mockData.js) and React state.

> ⚠️ Every person, address and reason here is invented. The site is public, so
> nothing in it refers to a real colleague or candidate. The set exists to cover
> each state the console has to render, not to look like a real roster.

## Where to see it

|                               |                                                                       |
| ----------------------------- | --------------------------------------------------------------------- |
| Live demo                     | https://circle-cat.github.io/purrf/#users                             |
| Locally, nothing else running | `bazel run //frontend:prototype_dev_server` → `/prototype.html#users` |

## The problem it illustrates

Purrf has no surface that answers "who is this person, and what state is their
account in". The answer is split across three places that do not link to each
other, and two things are visible from none of them: who blocked someone, and
whether someone is blocked at all. Separately, `is_active = false` has no writer
anywhere in the codebase — deactivating an account today means editing the
database by hand.

## Three views, one system

The view switcher at the top is not a demo convenience. Each entry is a
permission the design hands out **separately**, and what you can do changes
completely between them — which is the hardest part of this design to convey in
writing.

| View       | Permission                       | Can                                                                                               |
| ---------- | -------------------------------- | ------------------------------------------------------------------------------------------------- |
| Operations | `user.admin`                     | The console: search everyone, see and change account state, decide block requests, block directly |
| Recruiting | `recruiting.application.advance` | Raise a block request from the board — and nothing else                                           |
| Mentorship | `mentorship.admin.write`         | Raise a block request from the participant table — and nothing else                               |

State is shared across all three, so a request raised on Recruiting or
Mentorship appears in the Operations banner, and the decision made there flows
back to the row that raised it. A block is one process crossing three surfaces,
not three screens that mention the same person.

## Rules worth clicking on

- **Deactivated and blocked are orthogonal.** Open user 1250 (Liu, Kai): the
  row carries two chips at once. They are not steps on one scale — one is "the
  user no longer wants the account", the other is a sanction.
- **Raising a request changes nothing.** Switch to Mentorship, request a block
  on a participant, then look at them in Operations: still active, now carrying
  a third chip so no other operator acts on them blind.
- **The approver sees what approval will do — including what it won't.** Every
  block pre-flight lists the applications and interviews it sweeps _and_ names
  the mentorship pairs and meetings it leaves running, because blocking does not
  touch either. A screen showing only the first half would read as "handled".
- **A reason is mandatory, everywhere.** Blocking with an empty reason is not
  possible in either mode. The `users` table keeps current state, not history,
  so the reason is the only durable record of why this happened.
- **Deactivation asks for a note, and does not demand one.** It is not a
  sanction, so the copy carries no wrongdoing.
- **You cannot deactivate or block yourself.** Open user 1042 — both actions are
  disabled. Deactivating yourself locks you out of the console needed to undo it.
- **Search covers the block reason.** Type `no-show` into the search box. That
  is behaviour the recruiting blacklist page had, and absorbing that page must
  not lose it.
- **Permissions are a link, not a section.** The drawer ends with a link out to
  the permission-management page rather than embedding it. That page keeps its
  own gate; duplicating the check here would put one rule in two places.

## What this prototype deliberately does not show

- The permission-management page itself, which already ships and is unchanged.
- Removing or relinking a sign-in method. The console shows them read-only.
- The member-offboarding conversion (turning a departing employee's account into
  an external one).
- Auth0-side revocation. A blocked person can still sign in; every page just
  refuses them.

## Structure

| File                                 | Responsibility                                                          |
| ------------------------------------ | ----------------------------------------------------------------------- |
| `index.jsx`                          | Shell, view switcher, all shared state and transitions                  |
| `AccountsPage.jsx`                   | The operator's list: search, filters, pending-request banner            |
| `AccountDrawer.jsx`                  | One person: identity, state, sign-in methods, actions, pending decision |
| `BlockDialog.jsx`                    | Both blocking and requesting a block — same evidence, different verb    |
| `BlockImpact.jsx`                    | The pre-flight, including the untouched-mentorship warning              |
| `DeactivateDialog.jsx`               | Deactivation, with its optional note                                    |
| `DomainView.jsx`                     | Stands in for the board and mentorship management                       |
| `accountState.js` / `StateChips.jsx` | State derivation, and the chips that render it                          |
| `mockData.js`                        | Placeholder people, block impact, seeded request                        |

## Known limits

- Refreshing resets everything — no persistence of any kind.
- No router, so the view does not alter the URL (the `#users` hash selects the
  prototype, not the view within it).
- Each visitor gets an independent copy; nothing is shared between browsers.
