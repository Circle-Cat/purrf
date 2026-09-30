# Inbox Prototype

A self-contained, **mock-data** prototype of the service inboxes for inbound
mail. No backend, no auth. Everything comes from [`mockData.js`](./mockData.js)
and React state, and refreshing resets it.

> Every person and address here is made up, and all of them use reserved
> example domains.

Open it at `#inbox` (or `#inbox/recruiting`, `#inbox/inquiries` to start on
another inbox).

## What it demos

All aliases are Gmail Send-As aliases on one mailbox. New mail (not a reply on
a conversation that is already tracked) goes to the service inbox of the alias
it was sent to. Staff can reply, Archive, and Assign a thread to a person plus
whatever context that inbox needs.

| Inbox      | Alias                      | Where it lives in the product           | Assign to                                                                |
| ---------- | -------------------------- | --------------------------------------- | ------------------------------------------------------------------------ |
| Mentorship | `mentorship@circlecat.org` | A tab on the Mentorship management page | Person + round (defaults to the current round; `Not registered` allowed) |
| Recruiting | `recruiting@circlecat.org` | An entry on the Applications Board      | Person + an EMPLOYMENT job they applied to, which picks the application  |
| Inquiries  | `inquiries@circlecat.org`  | A new standalone page (placement TBD)   | Person only, or Move to the Mentorship / Recruiting inbox                |

Things to click:

- **One list per inbox.** By default it shows every thread that isn't
  archived, so a thread that is assigned and already replied to is still in
  the list. Threads that need a reply come first, newest inbound message
  first. After them come all the other threads, newest activity first. Two filter chips narrow it, and when both
  are on a thread has to match both. Their counts leave out archived threads:
  - _Needs reply_: the last human inbound message is newer than our last
    reply and newer than the archive time, whether or not the thread is
    assigned.
  - _Unassigned_: not assigned yet, whether or not anyone replied.

  Each row carries the same two words as tags when they apply. _Show archived_
  adds archived threads to the list. An archived thread never counts as
  Needs reply, so it only shows up under the Unassigned chip or with no chip
  on.

- **Search** matches the sender's name, user ID (`1555` or `#1555`), the
  sender's address (unknown senders included) and the subject. It ignores case
  and matches any part of the text. It combines with the chips and _Show
  archived_. The chip counts always cover every non-archived thread in the
  inbox and don't change with the search.

- **Reply** goes out from the alias of the inbox that owns the thread now. That
  line is read-only. A thread moved out of Inquiries replies from its new
  inbox's alias, and the conversation shows a note where the move happened. After you send, the thread no longer needs a reply.
- **Archive** hides a thread until a new inbound message arrives. Use
  _Dev: simulate new reply_ in the thread to see it come back.
- **Assigned threads come back** into Needs reply when the person writes
  again ("Requesting a different mentee", "Take-home assignment question").
- **Mentee application threads** ("Your mentee application") belong to the
  Mentorship inbox. They are tracked with their application, so they show no
  Assign button. The thread shows the alias change: the older outbound came
  from `recruiting@`, the newer one from `mentorship@`.
- **Sender matching** uses primary and alternative emails. "Can I still join
  the Fall round?" matches by alternative email. For an unknown sender you have
  to pick the person before you can assign.
- **Recruiting attaches to one application.** For Arjun Mehta, Backend Engineer
  attaches to #88 (In progress). For Sofia Ramirez, the only applications are
  rejected ones, so it attaches to the most recent, #57. Liam Novak has no
  employment application, so his thread can't be assigned.
- **Auto-replies and bounces** are dimmed and tagged. A bounce that no later
  send has replaced shows a "Delivery failed" banner.

## Fixed vs. draft

| Decision                                                                                                                 | Status                                                     |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| One mailbox, Send-As aliases, routing new mail by alias                                                                  | Fixed                                                      |
| One list, needs-reply first; combinable Needs reply / Unassigned filters and search                                      | Fixed                                                      |
| Reply alias is the owning inbox's alias and can't be chosen                                                              | Fixed                                                      |
| Mentorship assigns to a round, Recruiting to an application via its job                                                  | Fixed                                                      |
| Inquiries: Move to Mentorship / Recruiting inbox (arrives Unassigned, replies then go out from the target inbox's alias) | Fixed                                                      |
| Inquiries scope as a whole                                                                                               | **Draft**: still under discussion                          |
| Where the Inquiries page sits                                                                                            | **Draft**: placement TBD                                   |
| The three inboxes sharing one switcher                                                                                   | Prototype only; in the product each lives in its own place |

## Structure

| File               | Responsibility                                                      |
| ------------------ | ------------------------------------------------------------------- |
| `index.jsx`        | Inbox switcher, filter chips, all state and transitions             |
| `ThreadList.jsx`   | Rows: sender, subject, snippet, time, tags, assignment chip         |
| `ThreadDetail.jsx` | Conversation, actions, bounce banner, reply box                     |
| `AssignDialog.jsx` | Person picker, then round / job depending on the inbox              |
| `inboxState.js`    | All derived state: needs reply, archived, sender match, reply alias |
| `mockData.js`      | Made-up users, postings and threads                                 |
