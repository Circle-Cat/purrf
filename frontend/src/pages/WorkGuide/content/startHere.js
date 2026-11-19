import { GUIDE_PERMISSIONS } from "@/pages/WorkGuide/guideModel";

/**
 * The Start here chapter: how email and approvals work across Purrf. Open to
 * anyone who sees any part of the guide.
 *
 * @type {Object}
 */
export const START_HERE = {
  id: "start-here",
  title: "Start here",
  description: "How email and approvals work across Purrf.",
  permissions: GUIDE_PERMISSIONS,
  flows: [
    {
      id: "how-email-works",
      title: "How email works in Purrf",
      intro:
        "Purrf sends and reads email through one shared mailbox, and each kind of work has its own address on it. Which address a message goes to decides where it shows up in Purrf.",
      blocks: [
        {
          type: "table",
          columns: ["Address", "What it is for"],
          rows: [
            [
              "mentorship@circlecat.org",
              "The **Mentorship** inbox, and emails you send to a participant",
            ],
            [
              "recruiting@circlecat.org",
              "The **Recruiting** inbox, and emails you send to a candidate",
            ],
            [
              "contact@circlecat.org",
              "The **Contact** inbox: general questions, and the address under **Contact Us**",
            ],
            [
              "purrf@circlecat.org",
              "The mailbox itself. Mail sent straight to it lands in **Unsorted**",
            ],
            [
              "notification@circlecat.org",
              'Sends system emails only: copies of bell notifications ("Purrf Notifications") and Kit stage notifications. Replies to it are not collected in Purrf',
            ],
          ],
        },
        {
          type: "text",
          text: "**Where a reply goes.** A reply to an email you sent from an application or a participant page comes back to that page, not to the Inbox. A new email someone writes to one of the addresses above, without replying to anything, lands in the Inbox.",
        },
        { type: "diagram", name: "emailFlow" },
        {
          type: "text",
          text: "Only a reply goes back to the page it came from; every new email starts in the Inbox.",
        },
        {
          type: "text",
          text: "**What Purrf emails by itself**, so you don't send it again by hand:",
        },
        {
          type: "text",
          text: "Moving a mentor application to **Admitted** sends the new mentor a welcome email with the open round's dates. Mentees get no email.",
        },
        {
          type: "text",
          text: 'Every bell notification is also emailed to the person it is for, from "Purrf Notifications".',
        },
        {
          type: "text",
          text: "**What Purrf does not email**: advancing or rejecting an application does not tell the candidate. They see the new status on their own application page; write to them yourself if they should hear from you.",
        },
      ],
    },
    {
      id: "where-to-send-email",
      title: "Where to send email",
      intro:
        "To answer someone who wrote to us, reply in the **Inbox**; to write to someone first, go to their application page or participant page.",
      blocks: [
        {
          type: "table",
          columns: [
            "Where",
            "Use it to",
            "Sent from",
            "Replies show up in",
            "Who can use it",
          ],
          rows: [
            [
              "**Inbox** → open a conversation → **Send reply**",
              "Answer someone who wrote to one of our addresses",
              "That inbox's address; **Unsorted** replies from purrf@",
              "The same Inbox conversation",
              "Whoever sees that inbox",
            ],
            [
              "Application page → **Emails** tab → **Send email**",
              "Write first to a candidate about this application",
              "recruiting@",
              "The application's **Emails** tab",
              "A **Recruiter** of the posting with the recruiting advance permission",
            ],
            [
              "Participant page → **Send email**",
              "Write first to one participant about this round",
              "mentorship@",
              "The participant's **Timeline** for that round",
              "Mentorship write access",
            ],
            [
              "**Mentorship Management** → tick people → **Send notification · N**",
              "Send a stage email (for example **Match result**) to many people from a Kit draft",
              "notification@, through Kit",
              "Not collected in Purrf",
              "Mentorship write access",
            ],
            [
              "Application page → interview card → **Schedule meeting**",
              "Invite a candidate to an interview",
              "A Google Calendar invitation",
              "Google Calendar",
              "Recruiting advance permission",
            ],
          ],
        },
        {
          type: "steps",
          title: "Rules of thumb",
          steps: [
            {
              text: "A reply comes back to the place you sent from, so look for it there, not in the Inbox.",
            },
            {
              text: "One person → **Send email** on their page. Many people at one stage → **Send notification**.",
            },
            {
              text: 'Don\'t expect replies to Kit emails or to "Purrf Notifications" emails inside Purrf.',
            },
          ],
        },
      ],
    },
    {
      id: "how-approvals-work",
      title: "How approvals work in Purrf",
      intro:
        "Recruiting and mentorship each have their own approvals, described in their chapters; they all follow the same rules.",
      blocks: [
        {
          type: "goodToKnow",
          items: [
            "You pick one reviewer when you ask. Only that person can approve or reject, and nobody can review their own request.",
            "Nothing changes until the reviewer approves. Approving checks the conditions again; if they no longer hold (for example the round has ended), the approval is refused and the request stays open.",
            "Rejecting always needs a reason, and the person who asked sees it.",
            "While a request waits, only the person who asked can reassign it to another reviewer or withdraw it.",
            "The bell tells the reviewer when a request arrives, and tells you when it is decided; each bell item links to the page where it is decided.",
          ],
        },
      ],
    },
  ],
};
