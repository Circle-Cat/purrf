# Application Emails Prototype

The Emails tab of an application's detail page and its compose/reply dialog,
copied from the real UI with five proposed changes applied. Everything is mock
data, and refreshing resets the page.

Open it at `#application-emails`. Use the Application dropdown at the top to
switch between the three example applications.

## What it reproduces

These parts come from the real product:

- `EmailsPanel` from `frontend/src/pages/Recruiting/applications/ApplicationDetailPage.jsx`:
  the Send email / Refresh toolbar, threads with a Reply button, and message
  bubbles with sanitized HTML bodies.
- `frontend/src/pages/Recruiting/applications/ComposeEmailDialog.jsx`: To and
  Cc as comma-separated text, a template picker held at "" so every pick is an
  action, and a rich-text body with `[UPPERCASE]` markers highlighted. It also
  keeps the overwrite prompt, the unfilled-placeholder warning, the Cc prefill
  (`replyThread?.defaultCc ?? defaultCc`) and the `Re:` subject on replies.
- The templates are the eight real preset templates, filled for the selected
  application and signed by the sample recruiter.

Deliberate differences from the real UI:

- The template picker is a native select instead of a Radix Select, so jsdom
  tests can drive it.
- The signature is prefilled synchronously instead of after a fetch.
- Refresh only shows a note, because there is no mailbox to sync.
- The other tabs (Evaluations, Timeline, Comments) are empty placeholders.

## The five changes

1. **From line.** Compose and Reply show a read-only From. Mentor and mentee
   (ACTIVITY) postings send from `mentorship@circlecat.org`. EMPLOYMENT
   postings send from `recruiting@circlecat.org`.
2. **No default Cc to yourself.** A new email starts with an empty Cc. A reply
   prefills everyone copied earlier in the thread, except the candidate and
   our own aliases.
3. **From and To on every message**, plus Cc when there is one.
4. **Auto-replies and bounces** are tagged `Auto-reply` / `Delivery failed`
   and dimmed. A bounce shows "Delivery failed: your email to … was not
   delivered" until something is sent on that thread after it.
5. **Needs reply.** A thread shows Needs reply when the last message from a
   person is newer than our last reply and than the archive time. Auto-replies
   and bounces don't count. The Emails tab gets a dot while any thread needs a
   reply, and replying clears it. There is no Archive button on this page, so
   the archive part of the rule never comes into play here.

## Example applications

| Application                       | Posting    | Shows                                                                         |
| --------------------------------- | ---------- | ----------------------------------------------------------------------------- |
| Arjun Mehta · Backend Engineer    | EMPLOYMENT | A normal thread with a Cc to keep on reply, and a bounced thread              |
| Daniel Okafor · Mentee 2026       | ACTIVITY   | An older send from `recruiting@`, a newer one from `mentorship@`, Needs reply |
| Hana Kobayashi · Product Designer | EMPLOYMENT | An out-of-office auto-reply after our last message                            |

All people and addresses are made up. Candidates use example domains.

## Structure

| File                     | Responsibility                                               |
| ------------------------ | ------------------------------------------------------------ |
| `index.jsx`              | What-changed panel, application switcher, tabs, send handler |
| `EmailsPanel.jsx`        | Threads and messages                                         |
| `ComposeEmailDialog.jsx` | The composer                                                 |
| `emailState.js`          | Sender alias, Needs reply, bounce, reply Cc, templates       |
| `mockData.js`            | The three applications and their threads                     |
