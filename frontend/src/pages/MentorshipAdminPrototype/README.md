# Mentorship admin prototype

A self-contained, mock-data prototype of the redesigned mentorship admin
console. No backend, no auth, no environment variables. Refreshing resets
everything.

Open it at `#mentorship` in the Pages bundle.

## What it is showing

Four things are the design rather than decoration, and each is hard to convey
in a document.

**One table, pairs inside it.** There is no separate Pairs table. Each
person's row has a Pair column: a mentee's single active pair with the
meetings held and first contact (it is the mentee who reaches out, so the mark
is theirs), and a mentor's pairs one line each — Bob carries two mentees and is
still one row. The mid-term reminder is in the same row's Notifications, next
to the meeting count that decides whether it is needed. First contact is
stored on the pair, so a mentee who changes partner starts again at "not yet".

**Marking someone is not writing a note.** Three tags — no show, red flag,
partner change — are judgements with consequences, so the _Change status /
flag_ button raises a request instead of applying them. The note appears only once
somebody holding the approve permission decides it, and it is marked _(via
approval)_ so the next reader does not assume an admin typed it. Everything
else — a reminder having gone out, a phone call — is written straight from the
page.

**A request names a reviewer, but any approver can decide it.** Raising a
change means picking one person holding the approve permission, so the request
is addressed to someone rather than to a role. Anyone holding the permission
may still decide it — except whoever raised it. Switch _signed in as_ in the
header to see the same card from each approver's side. The raiser can withdraw
a request while it waits.

**Flags sit beside the status.** No show, red flag and partner change are
shown as badges next to a person's status, in the table and on their page,
because a flag does not end a status. Revoking one is itself a judgement, so it
is raised and approved like any other; the flag stays on the timeline, struck
through, and stops counting.

**Feedback has a direction.** The label always reads "_X's feedback about Y_",
never "pair feedback". On Cara's page this is what Cara wrote about a partner,
not what a partner wrote about Cara. A participant never sees what was written
about them; an admin does, because red flags have no other source.

**Emails and notes are one timeline.** On a participant's page, every message
Purrf sent and every reply pulled back in sits between the notes, newest
first, with a filter for either kind. There is no separate "an email went out"
note — the email itself is the entry. Internal members are reminded on Teams,
which Purrf never sees, so their timeline holds only the notes about it.

**Meetings belong to a pairing, not a person.** Each pair is a section on
the person's page, with its own meeting log. A mentor carrying two mentees has
two sections and two logs; adding them up would invent a number that does not
exist. The log itself is the console's existing meeting log — same columns,
three-state status, name-substituted attendance tags, batch Edit mode — moved
out of its dialog, not redrawn.

**Not registered is a filter too.** There is no Non-participants tab. While a
round is running — from its recruitment date to its feedback deadline — a line
above the table counts the people in the programme who have not registered
for it; _Show them_ (or the _Not registered for this round_ filter) lists
them. It is for sending the round's invitation and the onboarding reminders,
so a finished round does not offer it. "In the programme" means admitted to a
mentor or mentee posting, or registered for some round (the historical
backfill); an onboarding course on its own does not count. Notes work for
these people too, because a note is kept against a person and a round rather
than a registration.

**Every notification has a line.** The Notifications column lists each
notification of the round with a badge: Not notified, Notified (with
"manually" when it went out some other way and was recorded as a note), Failed
or Replied. The Notification filter picks a notification, then its state.
None of it is stored: it is read from the emails, the automatic admission
notice, and the notes that mark a notification sent by hand.

**Matching is a filter, not a table.** _Eligible for matching_ narrows the
table to who can go into a run now: not blocked or deactivated, training done,
not withdrawn, at least one free slot, and a clean history or an exemption
approved for this round. The rule is one function (`eligibility.js`), also
used to re-check a result when it is published. _Needs exemption_ lists who
would be eligible but for their history, only until the round's matching
closes.

## Try this

Toggle the permission chips in the header. They are four separate grants and
the page changes shape between them:

- Drop **Approve** — the pending card disappears entirely rather than greying
  out, and a request you raise just sits there.
- Drop **Feedback** — the feedback block on a participant vanishes. It is a
  separate grant because the read permission's holder count grows with
  everyone who wants to watch progress, and private opinions about a colleague
  should not grow with it.
- Drop **Write** — everything is still readable and nothing can be changed.

On Cara's page press _Refresh emails_: a reply that was waiting in the mailbox
comes in.

Filter the list, open a person, and press back: the same filter comes back,
because it lives in the URL.

Raise a partner change on a pair and approve it: the pair ends, its note and
status history stay on the pair's section, and the mentee is eligible again.

**Matching runs from the same filter.** Under _Eligible for matching_, pick
mentors and mentees and press _Run matching_. While it runs no other run can
start in the round. The review puts both people's résumés and applications
side by side with the reason; move a mentee or rewrite the reason, then _Save
draft_. A round's first publish is an approval; a later, supplemental run
publishes from its page. Either way the people in it are re-checked against
today — someone who withdrew or was blocked in the meantime stops it — and
whoever went in and still has no pair this round becomes unmatched; someone
already in a pair keeps their status. There is no matcher here: _Simulate the
run finishing_ stands in.

**An approval that no longer fits is not applied.** Approving re-reads the
target first. A no show for someone who has since withdrawn, a partner change
for a pair that has ended, a publish for a run that was replaced — each is
marked _Not applied_ with the reason, on the approvals card and the person's
page.

## What is deliberately missing

- What the export file contains. _Export for matching_ shows who goes in and
  with how many slots; the format is still being agreed with the algorithm
  side.
- Anything that talks to a server. Sending an email opens the composer and
  closes it; nothing is delivered.
