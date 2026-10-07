# Inbox Prototype

A self-contained, **mock-data** prototype of the Inbox for inbound mail. No
backend, no auth. Everything comes from [`mockData.js`](./mockData.js) and
React state, and refreshing resets it.

> Every person and address here is made up, and all of them use reserved
> example domains.

Open it at `#inbox` (or `#inbox/recruiting`, `#inbox/inquiries` to start
filtered to one service).

## What it demos

All aliases are Gmail Send-As aliases on one mailbox. New mail (not a reply on
a conversation that is already tracked) is tagged with the service of the
alias it was sent to. There is **one Inbox page** with one sidebar entry, and
every service's threads share one list. Which threads a viewer sees follows
their permissions, one per service:

| Service    | Alias                      | Permission                       | Assign to                                                                |
| ---------- | -------------------------- | -------------------------------- | ------------------------------------------------------------------------ |
| Mentorship | `mentorship@circlecat.org` | `mentorship.admin.write`         | Person + round (defaults to the current round; `Not registered` allowed) |
| Recruiting | `recruiting@circlecat.org` | `recruiting.application.advance` | Person + an EMPLOYMENT job they applied to, which picks the application  |
| Inquiries  | `inquiries@circlecat.org`  | `inquiries.manage` (new)         | Never assigned: Inquiries is just an inbox to reply from                 |

Things to click:

- **Sidebar entry.** The strip at the top stands in for the app sidebar: one
  _Inbox_ entry with the Needs reply count over every thread the viewer can
  see. _Dev: viewer permissions_ toggles the three permissions. Drop one and
  that service's threads, alias and filter disappear; drop all three and the
  entry is gone.
- **Service filter.** _All_ or one service, each with its Needs reply count.
  Each row and the open thread carry a coloured service tag.
- **One list.** By default it shows every thread that isn't archived, so a
  thread that is assigned and already replied to is still in the list.
  Threads that need a reply come first, newest inbound message first. After
  them come all the other threads, newest activity first. Two filter chips
  narrow it, and when both are on a thread has to match both. Their counts
  cover the selected service and leave out archived threads:
  - _Needs reply_: the last human inbound message is newer than our last
    reply and newer than the archive time, whether or not the thread is
    assigned.
  - _Unassigned_: a Mentorship or Recruiting thread that isn't assigned yet,
    whether or not anyone replied. Inquiries threads never count, and neither
    do threads from a sender whose address matches no user (see below).

  _Show archived_ adds archived threads to the list. An archived thread never
  counts as Needs reply.

- **Search** matches the thread's person by name and user ID (`1555` or
  `#1555`), the raw sender address (including senders with no matching user)
  and the subject. The thread's person is the assignee if there is one,
  otherwise the user the sender's address matches. A query that is only
  digits (optionally `#` first) is a user ID and must match exactly: `155`
  does not find #1555, and digits are not matched against name, email or
  subject. Other queries ignore case and match any part of the text. The chip
  counts don't change with the search.

- **Reply** goes out from the alias of the service that owns the thread now.
  That line is read-only. There is no Cc in either direction: we don't show
  the Cc of incoming mail, and replies go to the sender only.
- **Send-time check.** Sending is refused when the thread got a new message
  after you opened it: _Dev: simulate colleague reply_ (or _simulate new
  reply_), then Send. The draft stays; Send again to send it as is. Your own
  sends don't trip it. There is no claiming a thread.
- **Archive** hides a thread until a new inbound message arrives. Use
  _Dev: simulate new reply_ in the thread to see it come back.
- **Move** works between any two services. The thread arrives Unassigned and
  not archived, replies then go out from the new service's alias, and the
  conversation shows a note where the move happened. If the viewer can't see
  the new service, the thread leaves their view.
- **Remove assignment** sits in the Reassign dialog. The thread goes back to
  Unassigned (or _No matching user_ if the sender matches no one).
- **Tracked application threads** ("Your mentee application") belong to their
  application from the start. Their service follows the job type, so they
  have neither Assign nor Move. The thread shows the alias change: the older
  outbound came from `recruiting@`, the newer one from `mentorship@`.
- **Attachments on inbound mail** are listed with name and size ("Resume for
  any open role", "Your mentee application"). Clicking one would fetch it
  from Gmail on demand and always save it as a file; nothing is stored in
  Purrf. We never send attachments.
- **Sender matching** uses primary and alternative emails. "Can I still join
  the Fall round?" matches by alternative email.
- **No matching user.** When the sender's address matches no user, the row
  says _No matching user_. Such threads don't get the Unassigned tag, because
  the normal flow is to reply and Archive. Assign stays available on
  Mentorship and Recruiting threads, since the sender may be an existing user
  writing from an address they never registered.
- **Recruiting attaches to one application.** For Arjun Mehta, Backend
  Engineer attaches to #88 (In progress). For Sofia Ramirez, the only
  applications are rejected ones, so it attaches to the most recent, #57.
  Liam Novak has no employment application, so his thread can't be assigned:
  reply and Archive, and assign it later if he applies.
- **Auto-replies and bounces** are dimmed and tagged. A bounce that no later
  send has replaced shows a "Delivery failed" banner.

## Fixed vs. open

| Decision                                                                             | Status    |
| ------------------------------------------------------------------------------------ | --------- |
| One mailbox, Send-As aliases, routing new mail by alias                              | Fixed     |
| One Inbox page and sidebar entry for all services; visibility per service permission | Fixed     |
| One list, needs-reply first; service filter, Needs reply / Unassigned, search        | Fixed     |
| Reply alias is the owning service's alias and can't be chosen                        | Fixed     |
| Mentorship assigns to a round, Recruiting to an application via its job              | Fixed     |
| Inquiries: reply, Archive and Move only; no Assign                                   | Fixed     |
| Move between any two services; tracked application threads can't move                | Fixed     |
| Remove assignment; send-time check instead of claiming                               | Fixed     |
| Inbound attachments downloadable; no outbound attachments; no Cc either way          | Fixed     |
| New mail addressed to several service aliases, or Bcc'd to one                       | Postponed |

## Structure

| File               | Responsibility                                                        |
| ------------------ | --------------------------------------------------------------------- |
| `index.jsx`        | Sidebar stand-in, permissions, filters, all state and transitions     |
| `ThreadList.jsx`   | Rows: sender, service, subject, snippet, time, tags, assignment chip  |
| `ThreadDetail.jsx` | Conversation, attachments, actions, bounce banner, send-time check    |
| `AssignDialog.jsx` | Person picker, then round / job by service; Remove assignment         |
| `inboxState.js`    | All derived state: needs reply, archived, sender match, assign / move |
| `mockData.js`      | Made-up services, users, postings and threads                         |
