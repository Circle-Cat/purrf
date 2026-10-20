# Dashboard and DataSearch e2e: side effects audit

What the internal activity Dashboard (`/dashboard`) and DataSearch
(`/datasearch`) call, whether any of it writes, and what the suite lets out.
Read from the code deployed on test (main at `4ea81a05`, 2026-10-16). Paths
are under `frontend/src/` and `backend/`.

## Requests the pages make

Every call goes through `internal_activity_service/internal_activity_controller.py`.
The services behind them are `internal_activity_service/*_service.py`.

| Page and moment                                    | Request                                                                               | Gate                              | Reads                                                                                                                                                       |
| -------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dashboard, on load and on Search                   | `POST /api/summary` `{startDate, endDate, includeTerminated, groups}`                 | `dashboard.activity_summary.read` | Redis: LDAP hashes, chat, calendar, Gerrit and Jira indexes                                                                                                 |
| DataSearch, on load (the source picker is mounted) | `GET /api/microsoft/chat/topics`                                                      | `internal_activity.read`          | Redis hash `MICROSOFT_CHAT_TOPICS` (see below)                                                                                                              |
|                                                    | `GET /api/google/chat/spaces`                                                         | `internal_activity.read`          | Redis                                                                                                                                                       |
|                                                    | `GET /api/jira/projects`, `GET /api/gerrit/projects`, `GET /api/calendar/calendars`   | `internal_activity.read`          | Redis                                                                                                                                                       |
| DataSearch, opening the LDAP picker                | `GET /api/microsoft/active/ldaps?groups[]=…`; with Include Terminated, `…/all/ldaps…` | `internal_activity.read`          | Redis LDAP hashes (`ldap_service.py`)                                                                                                                       |
| DataSearch, Chat tab                               | `POST /api/microsoft/chat/count`, `POST /api/google/chat/count`                       | `internal_activity.read`          | Redis sorted sets (`zcount`)                                                                                                                                |
| DataSearch, Jira tab                               | `POST /api/jira/brief`; opening a status row, `POST /api/jira/detail/batch`           | `internal_activity.read`          | Redis                                                                                                                                                       |
| DataSearch, Gerrit tab                             | `POST /api/gerrit/stats`                                                              | `internal_activity.read`          | Redis                                                                                                                                                       |
| DataSearch, Calendar tab                           | `POST /api/calendar/events`                                                           | `internal_activity.read`          | Redis                                                                                                                                                       |
| Personal Dashboard (not this layer)                | `POST /api/summary/me`                                                                | `dashboard.activity_summary.read` | LaunchDarkly flag check; without a confirmed CircleCat address (every test account, PUR-804) 403 before Redis; else as `/api/summary` for the caller's ldap |

Since PUR-777 (#728, #729) the Dashboard reads only `POST /api/summary`
(the member count is the number of rows it returns) and the LDAP list is
gated on `internal_activity.read`; `directory.microsoft_ldap.read` is gone
from the code. e2e-admin still holds a row for it in `user_permissions`; the
API no longer reports it, so it has been dropped from `lib/accounts.js`.

The POSTs are queries with a body; none of them writes. Every Redis call in
the services behind them is a read (`hgetall`, `hget`, `hkeys`, `smembers`,
`zrange`, `zcount`, `get`). No database query, no event, no notification, no
mail, no Pub/Sub.

The one exception: `GET /api/microsoft/chat/topics` on an empty
`MICROSOFT_CHAT_TOPICS` hash (`microsoft_meeting_chat_topic_cache_service.py:cache_chat_topics`)
reads the user and chat lists from Microsoft Graph and writes the meeting
chat topics into that Redis hash. It is a cache fill: the same Graph reads
and Redis write the sync does, no message is sent. On test the hash is
filled (the endpoint returned one topic in 0.3 s on 2026-10-16), so the
suite's calls are cache hits.

## Redis budget

Test's Redis is an Upstash free database: 500,000 commands a month, and a
pipeline is billed per command inside it. The activity queries fan out per
member (`internal_activity_service/*_service.py`):

- `POST /api/summary`: for every member of the chosen groups, one Teams
  `zcount`, one per Google Chat space, a `zrange` per calendar plus an
  `smembers` and a `get` per event, an `hgetall` per Gerrit week, and a
  `zrange` per Jira project (31 on test) plus an `hget` per finished issue.
  It takes groups, never people.
- The DataSearch POSTs: the same per member named; an empty `ldaps` list
  means every active intern and employee, and empty project or space lists
  mean all of them.

Repeated full runs used up a month of test's quota in a day (2026-10-17;
the database was replaced). Since PUR-810 (#764) the server keeps
activity query results in an in-process LRU (256 entries, one replica), so
repeating an identical query costs no Redis until the pod restarts or the
entry is pushed out, and when Redis answers short (quota spent) the
activity routes return 503 instead of a 500 or quietly low numbers. Neither
changes what a first query costs, and a 503 in a run means the quota is
gone. So:

- One test sends the server a whole-group summary: the first Dashboard
  test, for the Dashboard's default groups (37 people on 2026-10-17) over
  one fixed week, 2026-05-04 to 2026-05-10 (`weekQuery`). Gerrit was
  retired in May 2026, so no recent week has a merged CL; that one has
  activity in every column. Its rows are kept in
  `.state/dashboard-week.json` with the API they came from (`weekRows`).
  Global setup deletes that file at the start of every run, and `weekRows`
  never asks the server itself: without rows kept for this environment in
  this run, a test that needs them fails saying dashboard/01's first test
  did not run.
- Every other Dashboard summary is answered in the browser with those rows
  (`stubSummary`), except searches the server refuses before reading any
  activity (end before start: two `hgetall` for the LDAP lists; an empty
  group list: none).
- DataSearch queries name the week's two busiest members and span at most
  seven days. The permission spec names one made-up ldap and sends its
  summary with the end before the start.

By a reading of the code (not measured), that puts a dashboard-layer run
at roughly 2,000 to 3,000 commands, most of it the one whole-group
summary; before, it was on the order of 100,000, half of that five
half-year summaries of every active member only to pick people. Keep new
tests inside these lines.

## What the suite lets out

Nothing these pages call changes data, so `lib/guard.js` lists their POSTs
with the other read-style calls (`READ_STYLE_CALLS`): `/api/summary`,
`/api/summary/me`, `/api/microsoft/chat/count`, `/api/google/chat/count`,
`/api/jira/brief`, `/api/jira/detail/batch`, `/api/gerrit/stats`,
`/api/calendar/events`. They go out even in `@smoke` tests and on staging.
Any other write from these pages would be refused by the guard.

The only write the layer makes itself is in the permission spec: for one
test it inserts a `user_permissions` row (`dashboard.activity_summary.read`
or `internal_activity.read`, `granted_source = 'admin'`) for e2e-readonly
and deletes that row by id when the test ends. If a run dies in between,
global setup refuses the next run ("also holds …; revoke them").

## What is real data

The activity data on test is what the prod sync wrote (prod copy plus
test's own sync). The specs compare the page with the response it got and
with the LDAP list from the API, never with fixed numbers. Names in the LDAP
picker are real people's directory names; they appear in traces.

## Not covered

- The server's summary rows beyond the one week of the Dashboard's default
  groups: volunteers, terminated members, and an idle period are checked
  only as the page sends and draws them (stubbed answers), the idle period
  also per source for two members in DataSearch.

- The Graph cache fill described above (would need an empty hash on test).
- Sorting in the DataSearch tables (same `Table` component as the Dashboard,
  whose sorting is covered).
