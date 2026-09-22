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
partner change — are judgements with consequences, so the button that looks
like it applies them actually raises a request. The note appears only once
somebody holding the approve permission decides it, and it is marked *(via
approval)* so the next reader does not assume an admin typed it. Everything
else — a reminder having gone out, a phone call — is written straight from the
page.

**Feedback has a direction.** The label always reads "*X's feedback about Y*",
never "pair feedback". On Cara's page this is what Cara wrote about a partner,
not what a partner wrote about Cara. A participant never sees what was written
about them; an admin does, because red flags have no other source.

**Meetings belong to a pairing, not a person.** They are on the pair page. A
mentor carrying two mentees has two meeting logs, and flattening them onto one
page would invent a number that does not exist.

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

## What is deliberately missing

- The matching run and review screen. That work is waiting on the export
  format the algorithm side needs.
- Anything that talks to a server. Sending an email opens the composer and
  closes it; nothing is delivered.
