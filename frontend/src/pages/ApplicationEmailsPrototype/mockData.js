/**
 * Placeholder applications and their email threads for the application
 * emails prototype.
 *
 * The bundle is published to a public URL, so every person and address here
 * is invented. Candidates use example domains; staff use made-up names on the
 * circlecat.org domain. The message shape follows what the real emails
 * endpoint returns (`threadId`, `messageId`, `direction`, `fromAddress`,
 * `bodyHtml`, `gmailInternalDate`), plus the fields this prototype adds: `to`,
 * `cc` and `kind`.
 */

/** The signed-in recruiter. Today their address is the default Cc. */
export const CURRENT_USER = {
  userId: 1042,
  name: "Morgan Lee",
  email: "morgan.lee@circlecat.org",
};

/** Send-As aliases on the one shared mailbox. */
export const ALIASES = {
  recruiting: "recruiting@circlecat.org",
  mentorship: "mentorship@circlecat.org",
  inquiries: "inquiries@circlecat.org",
};

/** The timezone the page formats times in (the viewer's, in the product). */
export const VIEWER_TIMEZONE = "America/Los_Angeles";

const R = ALIASES.recruiting;
const M = ALIASES.mentorship;
const DAEMON = "mailer-daemon@googlemail.com";
const HIRING_MANAGER = "priya.shah@circlecat.org";

const msg = (fields) => ({ cc: [], kind: "human", ...fields });

export const INITIAL_APPLICATIONS = [
  {
    id: 88,
    applicant: { name: "Arjun Mehta", email: "arjun.mehta@example.com" },
    job: { title: "Backend Engineer", kind: "EMPLOYMENT" },
    stage: "Behavioral",
    threads: [
      {
        threadId: 8801,
        subject: "Circle Cat Program - Interview Availability",
        archivedAt: null,
        messages: [
          msg({
            messageId: "8801-1",
            direction: "outbound",
            fromAddress: R,
            to: ["arjun.mehta@example.com"],
            cc: [HIRING_MANAGER],
            gmailInternalDate: "2026-09-20T17:05:00Z",
            bodyHtml:
              "<p>Dear Arjun Mehta,</p><p>I received your application from a colleague for Backend Engineer and we're definitely interested in speaking with you!</p><p>Please provide 5-6 dates/times over the next 1-2 weeks that will work for your schedule.</p><p>Best,<br><strong>Morgan Lee</strong><br>Director of People Operations<br>Circle Cat Inc</p>",
          }),
          msg({
            messageId: "8801-2",
            direction: "inbound",
            fromAddress: "arjun.mehta@example.com",
            to: [R],
            cc: [HIRING_MANAGER],
            gmailInternalDate: "2026-09-21T03:40:00Z",
            bodyHtml:
              "<p>Hi Morgan,</p><p>Thanks! I am free Tuesday or Thursday from 9PM ET, or any time Saturday.</p><p>Arjun</p>",
          }),
          msg({
            messageId: "8801-3",
            direction: "outbound",
            fromAddress: R,
            to: ["arjun.mehta@example.com"],
            cc: [HIRING_MANAGER],
            gmailInternalDate: "2026-09-22T16:30:00Z",
            bodyHtml:
              "<p>Dear Arjun Mehta,</p><p>Your interview has been scheduled for Thursday, October 1 at 9PM ET. You will receive a Google Meet invitation shortly.</p><p>Best,<br><strong>Morgan Lee</strong><br>Director of People Operations<br>Circle Cat Inc</p>",
          }),
        ],
      },
      {
        threadId: 8802,
        subject: "Your Circle Cat Technical Interview is Scheduled",
        archivedAt: null,
        messages: [
          msg({
            messageId: "8802-1",
            direction: "outbound",
            fromAddress: R,
            to: ["arjun.m@oldmail.example.org"],
            gmailInternalDate: "2026-09-25T18:00:00Z",
            bodyHtml:
              "<p>Dear Arjun Mehta,</p><p>We are looking forward to speaking with you! Your technical interview has been scheduled for October 6 at 10PM ET.</p><p>Best,<br><strong>Morgan Lee</strong><br>Director of People Operations<br>Circle Cat Inc</p>",
          }),
          msg({
            messageId: "8802-2",
            direction: "inbound",
            fromAddress: DAEMON,
            to: [R],
            kind: "bounce",
            bouncedTo: "arjun.m@oldmail.example.org",
            gmailInternalDate: "2026-09-25T18:01:00Z",
            bodyText:
              "Address not found. Your message wasn't delivered to arjun.m@oldmail.example.org because the address couldn't be found, or is unable to receive mail.",
          }),
        ],
      },
    ],
  },
  {
    id: 41,
    applicant: { name: "Daniel Okafor", email: "daniel.okafor@example.com" },
    job: { title: "Mentee 2026", kind: "ACTIVITY" },
    stage: "Recruiter screening",
    threads: [
      {
        threadId: 4101,
        subject: "Your mentee application",
        archivedAt: null,
        messages: [
          msg({
            messageId: "4101-1",
            direction: "outbound",
            fromAddress: R,
            to: ["daniel.okafor@example.com"],
            gmailInternalDate: "2026-08-30T17:00:00Z",
            bodyHtml:
              "<p>Dear Daniel Okafor,</p><p>We received your application for Mentee 2026. We will be in touch after the registration window closes.</p><p>Best,<br><strong>Morgan Lee</strong><br>Director of People Operations<br>Circle Cat Inc</p>",
          }),
          msg({
            messageId: "4101-2",
            direction: "outbound",
            fromAddress: M,
            to: ["daniel.okafor@example.com"],
            cc: ["mentor.team@circlecat.org"],
            gmailInternalDate: "2026-09-20T21:12:00Z",
            bodyHtml:
              "<p>Dear Daniel Okafor,</p><p>Your application has moved to the next step. Please complete the onboarding course before October 10.</p><p>Best,<br><strong>Morgan Lee</strong><br>Director of People Operations<br>Circle Cat Inc</p>",
          }),
          msg({
            messageId: "4101-3",
            direction: "inbound",
            fromAddress: "daniel.okafor@example.com",
            to: [M],
            cc: ["mentor.team@circlecat.org"],
            gmailInternalDate: "2026-09-29T15:47:00Z",
            bodyHtml:
              "<p>Thank you! The course link opens a blank page for me. Is there another way to access it?</p><p>Daniel</p>",
          }),
        ],
      },
    ],
  },
  {
    id: 104,
    applicant: { name: "Hana Kobayashi", email: "hana.kobayashi@example.com" },
    job: { title: "Product Designer", kind: "EMPLOYMENT" },
    stage: "Tech",
    threads: [
      {
        threadId: 10401,
        subject: "Scheduling your first interview",
        archivedAt: null,
        messages: [
          msg({
            messageId: "10401-1",
            direction: "inbound",
            fromAddress: "hana.kobayashi@example.com",
            to: [R],
            gmailInternalDate: "2026-09-25T15:00:00Z",
            bodyHtml:
              "<p>Hello, I can do any afternoon next week for the first interview.</p><p>Hana</p>",
          }),
          msg({
            messageId: "10401-2",
            direction: "outbound",
            fromAddress: R,
            to: ["hana.kobayashi@example.com"],
            gmailInternalDate: "2026-09-26T18:00:00Z",
            bodyHtml:
              "<p>Dear Hana Kobayashi,</p><p>Great, does Wednesday at 3PM ET work?</p><p>Best,<br><strong>Morgan Lee</strong><br>Director of People Operations<br>Circle Cat Inc</p>",
          }),
          msg({
            messageId: "10401-3",
            direction: "inbound",
            fromAddress: "hana.kobayashi@example.com",
            to: [R],
            kind: "auto_reply",
            gmailInternalDate: "2026-09-26T18:01:00Z",
            bodyText:
              "Out of office: I am travelling and will reply after September 30.",
          }),
        ],
      },
    ],
  },
];
