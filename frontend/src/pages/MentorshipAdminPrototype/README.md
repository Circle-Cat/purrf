# Mentorship admin prototype

A self-contained, mock-data prototype of the redesigned mentorship admin
console. No backend, no auth, no environment variables. Refreshing resets
everything.

Open it at `#mentorship` in the Pages bundle.

## What it is showing

Four things are the design rather than decoration, and each is hard to convey
in a document.

**One mentor, two mentees.** Bob Liu is a single row under *Participants* and
two rows under *Pairs*. That is the whole reason the search is split in two: a
question about a person ("has she registered?") and a question about a pairing
("have they met yet?") cannot be answered by the same row. Today's console
answers both from one table, which is why a mentor with two mentees appears
twice with no visible reason.

**Marking someone is not writing a note.** Three tags — no show, red flag,
partner change — are judgements with consequences, so the *Change status /
flag* button raises a request instead of applying them. The note appears only once
somebody holding the approve permission decides it, and it is marked *(via
approval)* so the next reader does not assume an admin typed it. Everything
else — a reminder having gone out, a phone call — is written straight from the
page.

**A request names a reviewer, but any approver can decide it.** Raising a
change means picking one person holding the approve permission, so the request
is addressed to someone rather than to a role. Anyone holding the permission
may still decide it — except whoever raised it. Switch *signed in as* in the
header to see the same card from each approver's side. The raiser can withdraw
a request while it waits.

**Flags sit beside the status.** No show, red flag and partner change are
shown as badges next to a person's status, in the table and on their page,
because a flag does not end a status. Revoking one is itself a judgement, so it
is raised and approved like any other; the flag stays on the timeline, struck
through, and stops counting.

**Feedback has a direction.** The label always reads "*X's feedback about Y*",
never "pair feedback". On Cara's page this is what Cara wrote about a partner,
not what a partner wrote about Cara. A participant never sees what was written
about them; an admin does, because red flags have no other source.

**Emails and notes are one timeline.** On a participant's page, every message
Purrf sent and every reply pulled back in sits between the notes, newest
first, with a filter for either kind. There is no separate "an email went out"
note — the email itself is the entry. Internal members are reminded on Teams,
which Purrf never sees, so their timeline holds only the notes about it.

**Meetings belong to a pairing, not a person.** They are on the pair page. A
mentor carrying two mentees has two meeting logs, and flattening them onto one
page would invent a number that does not exist. The log itself is the console's
existing meeting log — same columns, three-state status, name-substituted
attendance tags, batch Edit mode — moved out of its dialog, not redrawn.
There is no "add a meeting": the console cannot create one today, and moving
the log is not the place to start.

**Matching is a filter, not a table.** *Eligible for matching* on the
Participants tab narrows it to who can go into a run now: onboarding done, not
withdrawn, and at least one free slot. A matched mentee with an active pair, or
a mentor at their cap, drops out; a mentor with a place left stays, and is
exported with the slots left rather than the cap. Only under this filter do
"Free slots" and "Meetings last round" appear — they are signals for choosing
who to match and mean nothing the rest of the round.

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

Then select two rows on the *Pairs* tab and look at the send button: two pairs
is four people. A count of selected rows would be a lie there.

On Cara's page press *Refresh emails*: a reply that was waiting in the mailbox
comes in. Send a mid-term reminder to a pair from the *Pairs* tab and the
mentee's cell stamps itself; the manual mark is still there for Teams.

Filter the *Pairs* tab, open a pair, and press back: the same tab and the same
filter come back, because they live in the URL. The link in the address bar
can be sent to someone else and opens on that filtered list.

Open a pair and raise a partner change from there, then approve it: the note
and the status history appear on that pair's page. A request raised without
the pair it is about would never reach it.

## What is deliberately missing

- The matching run and review screen. That work is waiting on the export
  format the algorithm side needs.
- What the export file contains. *Export for matching* shows who goes in and
  with how many slots; the format is still being agreed with the algorithm
  side.
- Anything that talks to a server. Sending an email opens the composer and
  closes it; nothing is delivered.
