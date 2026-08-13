# Leave & PTO Prototype

A self-contained, **mock-data** prototype of the leave and annual-leave design,
built for stakeholder review. No backend, no auth, no env vars — everything
renders from [`mockData.js`](./mockData.js) and React state.

> ⚠️ **Every policy figure here is a placeholder, not the real policy.** This
> prototype is published to a public URL, so entitlements, the weekend
> arrangement, and the company holiday calendar are deliberately invented. What
> it demonstrates is the *mechanism* — accrual, deduction, approval, advance
> notice — not the numbers. Real figures live in the internal engineering spec.

## Where to see it

| | |
|---|---|
| Live demo | https://circle-cat.github.io/purrf/#leave |
| Locally, nothing else running | `bazel run //frontend:prototype_dev_server` → `/prototype.html#leave` |
| Inside the full app | route `/leave/prototype` — **needs a backend**, see below |

```bash
bazel run //frontend:prototype_dev_server
# open http://localhost:5273/prototype.html#leave
```

That target serves `prototype.html`, whose entry mounts the prototype bare — no
Auth0, no LaunchDarkly, no router, no API. It is the only way to view this
locally with nothing else up.

`bazel run //frontend:dev_server` boots the **full** app instead. The
`/leave/prototype` route inside it has no permission check, but the app shell
around it still authenticates, so that path needs a working backend and login.

### Or serve the static bundle, with no Node at all

```bash
bazel build //frontend:prototype_dist
python3 -m http.server -d bazel-bin/frontend/dist-pages 8080
# open http://localhost:8080/prototype.html#leave
```

This is byte-for-byte what GitHub Pages serves: one HTML file, one JS bundle,
one stylesheet, relative asset paths. Any static file server will do.

### Why there is no backend to remove

The prototypes never touch one. `prototype.html` loads `prototype-main.jsx`,
which does not import `App.jsx` or `main.jsx` — the two files that pull in
Auth0 and LaunchDarkly. Those files still exist in the branch, for the full
app, but nothing on this path loads them, so deleting them would change
nothing here and break the app.

Verified against the built bundle rather than assumed: no Auth0 or
LaunchDarkly string survives in it, and the only absolute URLs are mock
résumé links that are rendered as `href` and never fetched, framework error-doc
links, and SVG namespace constants.

The GitHub Pages bundle serves both prototypes behind a hash switch —
`#recruiting` and `#leave` — wired up in
[`src/PrototypeSwitcher.jsx`](../../PrototypeSwitcher.jsx). Everything else about
the Pages deploy is unchanged; see the
[recruiting prototype README](../RecruitingPrototype/README.md).

## What's in it

Three role views share one set of state, so a request submitted on the Employee
page appears in the Manager queue, and the decision made there flows back to the
employee's balance. That coupling is the point — the design is one system, not
three screens.

| View | Component | What it shows |
|---|---|---|
| Employee | `EmployeeView.jsx` | The personal-dashboard card and everything its buttons lead to |
| Manager | `ManagerView.jsx` | Approval queue, each card showing the requester's balance *after* approval |
| Administrator | `AdminView.jsx` | Calendar entry, policy, data health, balances, manual adjustments |

The employee side is arranged the way it will ship: one card on the personal
dashboard — three figures and four buttons, never growing — plus the places
those buttons lead.

| Button | Goes to | Why |
|---|---|---|
| Request time off | `RequestDialog.jsx` | Frequent, and you want to land back on the dashboard |
| Company holidays | `HolidaysDialog.jsx` | Short reference list, glance and close |
| My requests | `RequestsPage.jsx` | Scrolled back through; will want filtering later |
| Balance history | `LedgerPage.jsx` | Same, and it only grows |

The two pages are real routes in the shipped version. This bundle has no
router, so they swap in behind a back link — the same shape, minus the URL.

## Rules worth clicking on

The behaviour that is easy to miss in a written spec, and the fastest way to see
each one:

- **Not every requested day is deducted.** Pick a range spanning a weekend or a
  company holiday — the form lists which days it skipped and why.
- **Short notice is a flag, not a block.** Requesting *n* days needs *2n* working
  days of notice. Paid leave submits anyway with a warning the manager sees;
  a holiday exchange is refused outright.
- **A break can be part-exchanged.** Work two days of a three-day break and the
  third stays yours. Pick a range inside the break; the request covers only what
  you picked.
- **Exchange is all-or-nothing over its range.** Whether a break can be traded
  is decided for the break as a whole, but a range can still reach past one —
  the calendar can skip a day mid-break, and the day after a break is an
  ordinary working day. Include a day that does not qualify and the whole
  request is refused, naming the day — rather than silently crediting you for
  less than you worked.
- **Short sick leave skips approval.** Three days or less is approved on
  submission and never touches the balance. Longer goes to the manager, still
  without touching the balance.
- **Overdraft is allowed.** Request more than the balance and it submits, marked,
  with the resulting negative balance shown to the manager.
- **Nothing is submitted twice for the same day.** Overlapping an existing
  request is refused, across every leave type.
- **The ledger only grows.** Cancelling an approved request writes a reversal
  row rather than editing the original.
- **A missing calendar day cannot be caught by a total.** On Administrator →
  Calendar, delete one statutory day and watch the payout table: every period
  is re-priced, one break splits in two, and the annual total still comes to
  exactly the entitlement — because it is divided out of the entitlement rather
  than summed from the days. That table is the only place the mistake shows.

### What the admin calendar does not do here

Editing the calendar changes the payout table but does **not** reprice the
Employee tab. The calculator reads its holidays once at module load, and
threading a live calendar through it would be a refactor that buys the
prototype nothing.

## Structure

| File | Responsibility |
|---|---|
| `index.jsx` | Shell, role nav, all shared state and transitions |
| `CalendarAdmin.jsx` | Both calendars, read-only — they are loaded into the database once a year |
| `leaveCalc.js` | Working days, hour breakdown, advance notice, validation |
| `mockData.js` | Placeholder policy, people, seeded ledger and requests |
| `EmployeeView.jsx` / `ManagerView.jsx` / `AdminView.jsx` | The three views |

`leaveCalc.js` holds a single definition of "working day", shared by deduction,
advance notice, and the sick-leave threshold. The spec is explicit that a second
definition must never appear; the prototype mirrors that so the demo cannot
drift from the design it is illustrating.

## Known limits

- Refreshing resets everything — there is no persistence of any kind.
- No router, so page changes do not alter the URL and cannot be deep-linked
  (the `#leave` hash selects the prototype, not the page within it).
- Each visitor gets an independent copy; nothing is shared between browsers.
