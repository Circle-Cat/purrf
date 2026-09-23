import { beforeEach, describe, it, expect } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import MentorshipAdminPrototype from "@/pages/MentorshipAdminPrototype";
import {
  describeLastRound,
  lastRoundOf,
} from "@/pages/MentorshipAdminPrototype/lastRound";
import {
  INITIAL_PAIRS,
  INITIAL_PARTICIPANTS,
  INITIAL_ROUNDS,
} from "@/pages/MentorshipAdminPrototype/mockData";

/** The permission chips are their own labelled group; card buttons are not. */
const chip = (name) =>
  within(screen.getByRole("group", { name: "Permissions" })).getByRole(
    "button",
    { name },
  );

/**
 * A pair's line in the table. It appears on both people's rows — once on the
 * mentor's, once on the mentee's — so the first is as good as any.
 */
const pairLine = (mentor, mentee) =>
  screen.getAllByRole("listitem", { name: `Pair ${mentor} and ${mentee}` })[0];
const pairLines = (mentor, mentee) =>
  screen.queryAllByRole("listitem", { name: `Pair ${mentor} and ${mentee}` });

/** A person's row, found by the button with their name. */
const personRow = (name) =>
  screen
    .getAllByRole("row")
    .find((row) => within(row).queryByRole("button", { name }));

/** One pending request on the approvals card, found by its target. */
const pendingItem = (text) =>
  screen.getAllByRole("listitem").find((li) => li.textContent.includes(text));

const JASMINE = "2002";

const chooseReviewer = (userId = JASMINE) =>
  fireEvent.change(screen.getByLabelText("Reviewer"), {
    target: { value: userId },
  });

const signInAs = (userId) =>
  fireEvent.change(screen.getByLabelText("Signed in as"), {
    target: { value: userId },
  });

const raise = (reason) => {
  fireEvent.click(screen.getByRole("button", { name: "Change status / flag" }));
  fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
    target: { value: reason },
  });
  chooseReviewer();
  fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
};

beforeEach(() => {
  window.history.replaceState(null, "", window.location.pathname);
  window.sessionStorage.clear();
});

describe("MentorshipAdminPrototype smoke", () => {
  it("renders the console and walks the flows that carry the design", () => {
    render(<MentorshipAdminPrototype />);

    expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    expect(screen.getByText(/2 waiting/)).toBeInTheDocument();

    // "Meetings last round" only means something while choosing who to match.
    expect(screen.queryByText("Meetings last round")).not.toBeInTheDocument();

    // One table: Bob carries two mentees and is still one row, with a line
    // for each of his pairs.
    expect(screen.queryByRole("button", { name: "Pairs" })).toBeNull();
    expect(
      within(personRow("Liu, Bob")).getAllByRole("listitem", {
        name: /^Pair Liu, Bob and/,
      }),
    ).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("Participation history")).toBeInTheDocument();

    // Feedback always names whose opinion it is.
    expect(screen.getByText(/Wang, Cara's feedback about/)).toBeInTheDocument();

    // Her pair is on her own page, open: no separate pair page to go to.
    expect(
      screen.getByRole("button", { name: /with Liu, Bob/, expanded: true }),
    ).toBeInTheDocument();
    expect(screen.getByText("Meeting log")).toBeInTheDocument();
    expect(screen.getByText("Notes about this pair")).toBeInTheDocument();
  });

  it("drops whole blocks rather than greying them out when a grant is missing", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(chip("Approve"));
    expect(screen.queryByText("Pending approvals")).not.toBeInTheDocument();

    fireEvent.click(chip("Feedback"));
    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    expect(screen.queryByText(/feedback about/)).not.toBeInTheDocument();
  });

  it("raises a request instead of writing the note directly", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(screen.getByRole("button", { name: "Wu, Dana" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Change status / flag" }),
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "No reply on either channel." },
    });
    const send = screen.getByRole("button", { name: "Send for approval" });
    expect(send).toBeDisabled();
    chooseReviewer();
    fireEvent.click(send);

    // The status has not moved — only a pending request exists.
    expect(screen.getAllByText("signed_up").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    expect(screen.getByText(/3 waiting/)).toBeInTheDocument();
  });

  it("comes back from a detail page to the same filter", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.change(screen.getByPlaceholderText("Search name or email"), {
      target: { value: "Bob" },
    });
    expect(screen.queryByRole("button", { name: "Wang, Cara" })).toBeNull();
    expect(window.location.hash).toContain("q=Bob");

    fireEvent.click(screen.getByRole("button", { name: "Liu, Bob" }));
    expect(screen.getByText("Meeting log")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    expect(screen.getByPlaceholderText("Search name or email")).toHaveValue(
      "Bob",
    );
    expect(screen.queryByRole("button", { name: "Wang, Cara" })).toBeNull();
  });

  it("puts a change raised from a pair on that pair's section once approved", () => {
    render(<MentorshipAdminPrototype />);

    // One way in: Bob's name. His pairs are all on his page.
    fireEvent.click(screen.getByRole("button", { name: "Liu, Bob" }));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Change partner — Liu, Bob and Wang, Cara",
      }),
    );
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Schedules stopped overlapping." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("Liu, Bob ↔ Wang, Cara")).getByRole("button", {
        name: "Approve",
      }),
    );

    // Approving it ends the pair: Cara has a free slot again and can be
    // matched with someone else.
    expect(within(pairLine("Liu, Bob", "Wang, Cara")).getByText("Ended"));
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(personRow("Wang, Cara")).toBeDefined();
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Liu, Bob" }));
    fireEvent.click(screen.getByRole("button", { name: /with Wang, Cara/ }));
    expect(
      screen.getByText(/Schedules stopped overlapping\. — raised by/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Request a partner change — approved/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Change partner — Liu, Bob and Wang, Cara",
      }),
    ).toBeNull();
  });

  it("shows a partner change raised from the mentor's page on the mentor's page too", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Liu, Bob" }));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Change partner — Liu, Bob and Wang, Cara",
      }),
    );
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Schedules stopped overlapping." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));

    // Listed with Erin's request on Bob's other pair; only his own can be
    // withdrawn by him.
    expect(
      screen.getByText(/Request a partner change \(Liu, Bob ↔ Wang, Cara\)/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    expect(
      screen.queryByText(/Request a partner change \(Liu, Bob ↔ Wang, Cara\)/),
    ).toBeNull();
  });

  it("ends the person's pair when a withdrawal is approved", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    raise("She has left the programme.");
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("She has left the programme.")).getByRole("button", {
        name: "Approve",
      }),
    );

    // Her pair has ended: still listed, marked Ended, nothing left to mark.
    const ended = pairLine("Liu, Bob", "Wang, Cara");
    expect(within(ended).getByText("Ended")).toBeInTheDocument();
    expect(within(ended).queryByRole("button")).toBeNull();
    expect(
      within(pairLine("Liu, Bob", "Ma, Erin")).queryByText("Ended"),
    ).toBeNull();
  });

  it("asks for an optional note before marking first contact, and bulk marks count as notified", () => {
    render(<MentorshipAdminPrototype />);

    // First contact sits on the mentee's row: it is the mentee who reaches out.
    fireEvent.click(
      within(personRow("Wang, Cara")).getByRole("button", {
        name: "Mark first contact — Wang, Cara",
      }),
    );
    expect(
      screen.getByText("First contact confirmed — Liu, Bob ↔ Wang, Cara"),
    ).toBeInTheDocument();
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Mark" }),
    );
    expect(
      within(personRow("Wang, Cara")).getByRole("button", {
        name: "First contact confirmed 2026-09-22 — Wang, Cara",
      }),
    ).toBeInTheDocument();
    // The mentor's row has no such mark.
    expect(
      within(personRow("Liu, Bob")).queryByRole("button", {
        name: /^(Mark first contact|First contact confirmed)/,
      }),
    ).toBeNull();

    fireEvent.click(within(personRow("Ma, Erin")).getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Mark as notified" }));
    expect(
      within(personRow("Ma, Erin")).getByRole("button", {
        name: "Mid-term reminder: notified manually 2026-09-22",
      }),
    ).toBeInTheDocument();
  });

  it("blocks someone from their page through an approval, ending their pairs", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Ma, Erin" }));
    fireEvent.click(screen.getByRole("button", { name: "Block from Purrf" }));
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Harassed her mentor." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("Harassed her mentor.")).getByRole("button", {
        name: "Approve",
      }),
    );

    expect(
      within(personRow("Ma, Erin")).getByText("Blocked"),
    ).toBeInTheDocument();
    expect(
      within(pairLine("Liu, Bob", "Ma, Erin")).getByText("Ended"),
    ).toBeInTheDocument();
    // Erin's own partner-change request no longer has a pair to act on.
    signInAs("2001");
    fireEvent.click(
      within(pendingItem("schedules no longer overlap")).getByRole("button", {
        name: "Approve",
      }),
    );
    expect(
      screen.getByRole("listitem", {
        name: /^Not applied: Request a partner change/,
      }),
    ).toHaveTextContent("This pair has already ended.");
  });

  it("has no way to mark people unmatched by hand", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(within(personRow("Chen, Alice")).getByRole("checkbox"));
    expect(
      screen.queryByRole("button", { name: /Confirm as unmatched/ }),
    ).toBeNull();
  });

  it("does not apply an approval the world has moved past, and says why", () => {
    render(<MentorshipAdminPrototype />);
    // Dana has a no show waiting; she withdraws before anyone decides it.
    fireEvent.click(screen.getByRole("button", { name: "Wu, Dana" }));
    raise("She has left the programme.");
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("She has left the programme.")).getByRole("button", {
        name: "Approve",
      }),
    );
    signInAs("2001");
    fireEvent.click(
      within(pendingItem("Missed both mentor briefings")).getByRole("button", {
        name: "Approve",
      }),
    );

    expect(
      screen.getByRole("listitem", {
        name: "Not applied: Mark as no show — Wu, Dana",
      }),
    ).toHaveTextContent("Wu, Dana has already withdrawn.");
    fireEvent.click(screen.getByRole("button", { name: "Wu, Dana" }));
    expect(screen.getByText("Not applied")).toBeInTheDocument();
    expect(screen.queryByText("No show")).toBeNull();
  });

  it("keeps emails and notes on one timeline, and Refresh pulls replies in", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));

    expect(screen.getAllByText("Email sent").length).toBeGreaterThan(0);
    expect(screen.getByText("Reply")).toBeInTheDocument();
    expect(screen.getByText(/Called her/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Emails only" }));
    expect(screen.queryByText(/Called her/)).not.toBeInTheDocument();

    expect(screen.queryByText(/we met twice/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh emails" }));
    expect(screen.getByText(/1 new reply/)).toBeInTheDocument();
    expect(screen.getByText(/we met twice/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Refresh emails" }));
    expect(screen.getByText(/no new replies/)).toBeInTheDocument();
  });

  it("puts a sent mid-term reminder on the timeline and in the Notifications column", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(within(personRow("Ma, Erin")).getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Send email · 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Send 1" }));

    expect(
      within(personRow("Ma, Erin")).getByRole("button", {
        name: "Mid-term reminder: notified by email 2026-09-22",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ma, Erin" }));
    expect(screen.getByText("Email sent")).toBeInTheDocument();
    expect(screen.getByText("Mid-term reminder")).toBeInTheDocument();
  });

  it("filters the person axis to who can be matched, and exports mentors with what they have left", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );

    expect(screen.getByText("Meetings last round")).toBeInTheDocument();
    expect(window.location.hash).toContain("filter=eligible");
    const poolRow = (name) =>
      screen
        .getAllByRole("row")
        .find((row) => within(row).queryByRole("button", { name }));

    // Matched with an active pair: no free slot, so not offered again.
    expect(poolRow("Wang, Cara")).toBeUndefined();
    expect(poolRow("Ma, Erin")).toBeUndefined();
    // Onboarding not done.
    expect(poolRow("Hu, Ivy")).toBeUndefined();
    // Matched, but a slot is still open.
    expect(within(poolRow("Liu, Bob")).getByText("1 of 3")).toBeInTheDocument();
    expect(within(poolRow("Guo, Fay")).getByText("2 of 2")).toBeInTheDocument();
    // The four states still read as four answers here.
    expect(
      within(poolRow("Chen, Alice")).getByText("First time"),
    ).toBeInTheDocument();
    // Their latest earlier round, told apart rather than turned into a 0.
    expect(
      within(poolRow("Wu, Dana")).getByText("Mentorship 2025 Summer · 7/7"),
    ).toBeInTheDocument();
    expect(
      within(poolRow("Liu, Bob")).getByText(
        "Mentorship 2025 Summer · Not matched",
      ),
    ).toBeInTheDocument();
    expect(
      within(poolRow("Guo, Fay")).getByText(
        "Mentorship 2025 Summer · Withdrawn at 2/7",
      ),
    ).toBeInTheDocument();

    fireEvent.click(within(poolRow("Liu, Bob")).getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Run matching · 1" }),
    ).toBeDisabled();
    fireEvent.click(within(poolRow("Chen, Alice")).getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Run matching · 2" }),
    ).toBeEnabled();
  });

  it("shows the existing meeting log on the pair page, editable only in a v2 round", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Ma, Erin" }));

    expect(screen.getByText("Ma, Erin absent")).toBeInTheDocument();
    expect(screen.getByText("Insufficient duration")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText("Incomplete")).toBeInTheDocument();
    expect(screen.getByText(/America\/Los_Angeles/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Delete \(1\)/ }));
    expect(screen.getByText("Delete meetings?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm changes" }));
    return waitFor(() =>
      expect(screen.queryByText("Ma, Erin absent")).not.toBeInTheDocument(),
    );
  });

  it("leaves a v1 round's meeting log read-only", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    fireEvent.click(screen.getByRole("button", { name: "Wu, Dana" }));
    expect(screen.getByText("Meeting log")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
  });

  it("sends a request to a named reviewer, and never lets the raiser decide it", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Wu, Dana" }));
    raise("Still no reply.");
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));

    const mine = pendingItem("Still no reply.");
    expect(within(mine).getByText(/You raised this/)).toBeInTheDocument();
    expect(within(mine).queryByRole("button", { name: "Approve" })).toBeNull();
    expect(
      within(mine).getByText(/Sent\s+to\s+Wang, Jasmine/),
    ).toBeInTheDocument();

    // Sent to Jasmine, but any approver may decide — Yanpei here.
    signInAs("2003");
    expect(
      within(pendingItem("Still no reply.")).getByRole("button", {
        name: "Approve",
      }),
    ).toBeInTheDocument();
  });

  it("lets the raiser withdraw a request while it waits", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Wu, Dana" }));
    raise("Raised by mistake.");

    expect(screen.getByText("Waiting on a decision")).toBeInTheDocument();
    const before = screen.getAllByRole("button", { name: "Withdraw" }).length;
    fireEvent.click(screen.getAllByRole("button", { name: "Withdraw" })[0]);
    expect(screen.queryAllByRole("button", { name: "Withdraw" })).toHaveLength(
      before - 1,
    );
  });

  it("shows standing flags beside the status, and revokes one through an approval", () => {
    render(<MentorshipAdminPrototype />);
    const caraRow = () =>
      screen
        .getAllByRole("row")
        .find((row) =>
          within(row).queryByRole("button", { name: "Wang, Cara" }),
        );
    expect(within(caraRow()).getByText("No show")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    expect(screen.getByText(/Revoke a flag/)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "She had emailed; it went to spam." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    // Nothing changes until someone else decides.
    expect(within(caraRow()).getByText("No show")).toBeInTheDocument();
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("went to spam")).getByRole("button", {
        name: "Approve",
      }),
    );
    expect(within(caraRow()).queryByText("No show")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    expect(screen.getByText("(revoked)")).toBeInTheDocument();
    expect(
      // On her timeline, and on the pair it was about.
      screen.getAllByText(/Revoked the No show of 2026-09-20/)[0],
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Revoke" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the matching columns off the table outside the filter", () => {
    render(<MentorshipAdminPrototype />);
    const filter = screen.getByRole("button", {
      name: "Eligible for matching",
    });

    fireEvent.click(filter);
    expect(screen.getByText("Free slots")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Wang, Cara" })).toBeNull();

    fireEvent.click(filter);
    expect(screen.queryByText("Free slots")).not.toBeInTheDocument();
    expect(screen.queryByText("Meetings last round")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Wang, Cara" }),
    ).toBeInTheDocument();
  });

  it("finds who has not registered this round, and invites them to the new one", () => {
    render(<MentorshipAdminPrototype />);
    expect(
      screen.queryByRole("button", { name: "Non-participants" }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(
        /3 people in the programme have not registered for Mentorship 2026 Fall/,
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));
    expect(window.location.hash).toContain("filter=unregistered");

    // Took part last summer, not signed up again: exactly who an invitation is for.
    const minRow = screen
      .getAllByRole("row")
      .find((row) => within(row).queryByText("Park, Min"));
    expect(
      within(minRow).getByText("Mentorship 2025 Summer"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Never")).toHaveLength(2);
    // Handed an onboarding course but never admitted: not in the programme.
    expect(screen.queryByText("Zhou, Tao")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select Osei, Kwame" }),
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Park, Min" }));
    expect(
      screen.getByRole("button", { name: "Mark as notified" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send email · 2" }));
    expect(
      within(screen.getByRole("dialog")).getByText("New round invitation"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send 2" }));

    expect(
      screen.getAllByText("New round invitation · 2026-09-22"),
    ).toHaveLength(2);
  });

  it("lists who has not registered only while the round is running", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));
    const rowOf = (name) =>
      screen.getAllByRole("row").find((row) => within(row).queryByText(name));
    // Took part last summer and not this autumn.
    expect(
      within(rowOf("Park, Min")).getByText("Mentorship 2025 Summer"),
    ).toBeInTheDocument();
    // Registered this autumn, so not on the list.
    expect(rowOf("Chen, Alice")).toBeUndefined();
    // Training comes from the course rows.
    expect(
      within(rowOf("Osei, Kwame")).getByText("in_progress"),
    ).toBeInTheDocument();

    // A finished round has nobody left to invite: the filter is off, and
    // switching to it drops the list.
    fireEvent.click(
      screen.getByRole("button", { name: "Mentorship 2025 Summer" }),
    );
    expect(
      screen.getByRole("button", { name: "Not registered for this round" }),
    ).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Show them" })).toBeNull();
    expect(rowOf("Osei, Kwame")).toBeUndefined();
  });

  it("lets notes be written about someone who has not registered", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));

    // In bulk, after inviting on Teams.
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Park, Min" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark as notified" }));

    fireEvent.click(screen.getByRole("button", { name: "Park, Min" }));
    expect(window.location.hash).toContain("participants/3111?round=7");
    expect(
      screen.getByText(/Not registered for this round/),
    ).toBeInTheDocument();
    expect(screen.getByText("Round invitation")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Change status / flag" }),
    ).not.toBeInTheDocument();

    // One at a time, from their page.
    fireEvent.click(screen.getByRole("button", { name: "Add a note" }));
    fireEvent.change(
      screen.getByPlaceholderText("Sent on Teams. No reply yet."),
      {
        target: { value: "Says he will sign up after his team offsite." },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText(/after his team offsite/)).toBeInTheDocument();

    // Last year's registration is still there to read.
    expect(screen.getByText("Participation history")).toBeInTheDocument();
    expect(screen.getByText("Mentorship 2025 Summer")).toBeInTheDocument();
  });

  it("shows each person's account state beside their round status", () => {
    render(<MentorshipAdminPrototype />);
    expect(screen.getByText("Account")).toBeInTheDocument();
    const rowOf = (name) =>
      screen.getAllByRole("row").find((row) => within(row).queryByText(name));

    expect(within(rowOf("Liu, Bob")).getByText("Active")).toBeInTheDocument();
    expect(
      within(rowOf("Shen, Gina")).getByText("Blocked"),
    ).toBeInTheDocument();
    expect(within(rowOf("Shen, Gina")).queryByText("Active")).toBeNull();
    expect(
      within(rowOf("Hu, Ivy")).getByText("Deactivated"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show them" }));
    // Independent flags: both at once.
    expect(
      within(rowOf("Rossi, Lia")).getByText("Deactivated"),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Rossi, Lia")).getByText("Blocked"),
    ).toBeInTheDocument();
  });

  it("never offers a blocked person to matching", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(screen.queryByRole("button", { name: "Lin, Oscar" })).toBeNull();
    // Gina and Oscar blocked, Ivy deactivated.
    expect(screen.getByText(/3 blocked or/)).toBeInTheDocument();
  });

  it("keeps people with a past to look at out of matching until an exemption is approved", () => {
    render(<MentorshipAdminPrototype />);
    // The pool itself is clean: nobody waiting on an exemption is in it.
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(screen.queryByRole("button", { name: "Kim, Sora" })).toBeNull();
    expect(screen.getByText(/2 waiting on an exemption/)).toBeInTheDocument();

    // Counted on the button without asking; listed when pressed.
    fireEvent.click(
      screen.getByRole("button", { name: "Needs exemption · 2" }),
    );
    expect(
      within(personRow("Kim, Sora")).getByText(
        "Met 3/7 in Mentorship 2025 Summer",
      ),
    ).toBeInTheDocument();
    expect(
      within(personRow("Tan, Wei")).getByText(
        "Red flag in Mentorship 2025 Summer",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Kim, Sora" }));
    expect(
      screen.getByText("Needs an exemption before being matched this round"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Request exemption" }));
    expect(
      screen.getByText("Exempt from the history check"),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Her mentor moved abroad mid-round; not on her." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("moved abroad")).getByRole("button", {
        name: "Approve",
      }),
    );
    // Out of the exemption list, into the pool; Wei is still waiting.
    expect(personRow("Kim, Sora")).toBeUndefined();
    expect(
      screen.getByRole("button", { name: "Needs exemption · 1" }),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(personRow("Kim, Sora")).toBeDefined();
  });

  it("hides what does not help choose who to match", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    for (const header of [
      "Int / ext",
      "Status",
      "Account",
      "Notifications",
      "Training",
    ]) {
      expect(screen.queryByRole("columnheader", { name: header })).toBeNull();
    }
    for (const header of [
      "Role",
      "Pair",
      "Free slots",
      "Meetings last round",
    ]) {
      expect(
        screen.getByRole("columnheader", { name: header }),
      ).toBeInTheDocument();
    }
  });

  const startRun = () => {
    const filter = screen.getByRole("button", {
      name: "Eligible for matching",
    });
    if (filter.getAttribute("aria-pressed") !== "true") fireEvent.click(filter);
    const row = (name) =>
      screen
        .getAllByRole("row")
        .find((r) => within(r).queryByRole("button", { name }));
    ["Liu, Bob", "Guo, Fay", "Chen, Alice", "Wu, Dana"].forEach((name) =>
      fireEvent.click(within(row(name)).getByRole("checkbox")),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run matching · 4" }));
  };

  it("runs matching on the chosen people, and holds the round while it runs", () => {
    render(<MentorshipAdminPrototype />);
    expect(
      screen.getByRole("button", { name: "View matching results" }),
    ).toBeDisabled();

    startRun();
    expect(window.location.hash).toContain("matching/7");
    expect(screen.getByText(/No other run can start/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    expect(
      screen.getByRole("button", { name: "Matching running…" }),
    ).toBeInTheDocument();
    const row = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Chen, Alice" }));
    fireEvent.click(within(row).getByRole("checkbox"));
    const bob = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Liu, Bob" }));
    fireEvent.click(within(bob).getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Run matching · 2" }),
    ).toBeDisabled();
  });

  it("reviews a result with both résumés, lets pairs and reasons be changed, then publishes", () => {
    render(<MentorshipAdminPrototype />);
    startRun();
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    expect(screen.getByText(/2 of 2\s+mentees matched/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^Chen, Alice/ }));
    // Both sides, résumé and application.
    expect(
      screen.getByText(/Data Analyst · Northwind Health/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Staff Software Engineer · Circle Cat/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/People moving into ML from analytics/),
    ).toBeInTheDocument();

    // Bob has one slot left; giving him Dana as well is over his cap.
    fireEvent.click(screen.getByRole("button", { name: /^Wu, Dana/ }));
    fireEvent.change(screen.getByLabelText("Mentor for Wu, Dana"), {
      target: { value: "3102" },
    });
    expect(
      screen.getByText(/Liu, Bob is given 2 mentees but has 1 slot left/),
    ).toBeInTheDocument();
    // Moving her cleared the reason written for her old mentor.
    expect(
      screen.getByText(/Wu, Dana is matched with no reason/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request publishing" }),
    ).toBeDisabled();

    // Send Alice to Fay instead and write both reasons.
    fireEvent.change(screen.getByLabelText("Mentor for Chen, Alice"), {
      target: { value: "3106" },
    });
    fireEvent.change(screen.getByLabelText("Reason for Chen, Alice"), {
      target: { value: "Fay hires for ML-adjacent roles." },
    });
    fireEvent.change(screen.getByLabelText("Reason for Wu, Dana"), {
      target: { value: "Bob can speak to leading a platform team." },
    });
    expect(screen.getAllByText("The matcher proposed")).toHaveLength(2);

    // Nothing is asked for until the edits are saved.
    expect(
      screen.getByRole("button", { name: "Request publishing" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    fireEvent.click(screen.getByRole("button", { name: "Request publishing" }));
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Reviewed every pair against both applications." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));

    // Locked while it waits, so what is approved is what gets published.
    expect(
      screen.getByText(/Waiting for approval to publish/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Mentor for Chen, Alice")).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("pairs from run")).getByRole("button", {
        name: "Approve",
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "View matching results" }),
    );
    expect(screen.getByText(/Published\./)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    const eligible = screen.getByRole("button", {
      name: "Eligible for matching",
    });
    if (eligible.getAttribute("aria-pressed") === "true") {
      fireEvent.click(eligible);
    }
    expect(pairLine("Guo, Fay", "Chen, Alice")).toBeInTheDocument();
    expect(pairLine("Liu, Bob", "Wu, Dana")).toBeInTheDocument();
  });

  it("keeps the reason within what the published column can hold", () => {
    render(<MentorshipAdminPrototype />);
    startRun();
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Chen, Alice/ }));
    fireEvent.change(screen.getByLabelText("Reason for Chen, Alice"), {
      target: { value: "x".repeat(301) },
    });
    expect(screen.getByText("301/300")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(
      screen.getByRole("button", { name: "Request publishing" }),
    ).toBeDisabled();
  });

  it("keeps edits on the page until the draft is saved, and can throw them away", () => {
    render(<MentorshipAdminPrototype />);
    startRun();
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /^Chen, Alice/ }));
    fireEvent.change(screen.getByLabelText("Reason for Chen, Alice"), {
      target: { value: "A different reason." },
    });
    expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request publishing" }),
    ).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(screen.queryByText(/Unsaved changes/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Reason for Chen, Alice")).not.toHaveValue(
      "A different reason.",
    );
    expect(
      screen.getByRole("button", { name: "Request publishing" }),
    ).toBeEnabled();
  });

  it("marks who came out of a run with no pair unmatched, and leaves anyone already paired alone", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    // Bob already has two mentees and a slot left; Dana will take Fay, and
    // Bob gets nobody new.
    ["Liu, Bob", "Guo, Fay", "Wu, Dana"].forEach((name) =>
      fireEvent.click(within(personRow(name)).getByRole("checkbox")),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run matching · 3" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    expect(screen.getByText(/Without a partner: Liu, Bob/)).toBeInTheDocument();
    expect(
      screen.getByText(/Publishing marks them unmatched, unless/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Request publishing" }));
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "One pair; Bob keeps his two." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));

    expect(pendingItem("pairs from run").textContent).toMatch(
      /1 unmatched: Liu, Bob/,
    );
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("pairs from run")).getByRole("button", {
        name: "Approve",
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(
      within(personRow("Liu, Bob")).getByText("matched"),
    ).toBeInTheDocument();
    expect(pairLine("Guo, Fay", "Wu, Dana")).toBeInTheDocument();
  });

  it("re-checks the people in a run when publishing is approved", () => {
    render(<MentorshipAdminPrototype />);
    startRun();
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Request publishing" }));
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Looks right." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));

    // Alice withdraws while the result waits.
    fireEvent.click(screen.getByRole("button", { name: "Chen, Alice" }));
    raise("Took a new job; no time this round.");
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("Took a new job")).getByRole("button", {
        name: "Approve",
      }),
    );
    fireEvent.click(
      within(pendingItem("Looks right.")).getByRole("button", {
        name: "Approve",
      }),
    );

    expect(
      screen.getByRole("listitem", { name: /^Not applied: Publish matching/ }),
    ).toHaveTextContent("Chen, Alice has withdrawn or been closed out.");
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(within(personRow("Chen, Alice")).getByText("withdrawn"));
    expect(
      screen.queryAllByRole("listitem", { name: /^Pair .* and Chen, Alice$/ }),
    ).toHaveLength(0);
  });

  it("invalidates a publish approval for a run that has since been replaced", () => {
    render(<MentorshipAdminPrototype />);
    startRun();
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Request publishing" }));
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "First run looks right." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));

    // Someone starts a fresh run, and it finishes, before the approval comes
    // in — so the only thing wrong with the old request is its run.
    startRun();
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("First run looks right.")).getByRole("button", {
        name: "Approve",
      }),
    );

    expect(
      screen.getByRole("listitem", { name: /^Not applied: Publish matching/ }),
    ).toHaveTextContent("A newer matching run has replaced this one.");
    expect(pairLines("Liu, Bob", "Chen, Alice")).toHaveLength(0);
  });

  it("publishes a supplemental run without an approval", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    ["Guo, Fay", "Chen, Alice"].forEach((name) =>
      fireEvent.click(within(personRow(name)).getByRole("checkbox")),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run matching · 2" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Request publishing" }));
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Main run." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("Main run.")).getByRole("button", { name: "Approve" }),
    );

    // A second run in the same round publishes from its own page.
    const eligible = screen.getByRole("button", {
      name: "Eligible for matching",
    });
    if (eligible.getAttribute("aria-pressed") !== "true") {
      fireEvent.click(eligible);
    }
    ["Liu, Bob", "Wu, Dana"].forEach((name) =>
      fireEvent.click(within(personRow(name)).getByRole("checkbox")),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run matching · 2" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    expect(
      screen.queryByRole("button", { name: "Request publishing" }),
    ).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: "Publish supplemental matches" }),
    );
    expect(screen.getByText(/Published\./)).toBeInTheDocument();
    expect(screen.getByText("Earlier published runs")).toBeInTheDocument();
  });

  it("shows where each person's emails stand, one dot per email of the round", () => {
    render(<MentorshipAdminPrototype />);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    // How far each person has got, in words, above the dots.
    const cara = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Wang, Cara" }));
    expect(
      within(cara).getByText("Mid-term reminder · 2026-09-18"),
    ).toBeInTheDocument();
    const alice = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Chen, Alice" }));
    expect(within(alice).getByText("Failed")).toBeInTheDocument();
    const rowOf = (name) =>
      screen
        .getAllByRole("row")
        .find((r) => within(r).queryByRole("button", { name }));

    // Replied, notified by email, notified manually, failed, not notified.
    expect(
      within(rowOf("Wang, Cara")).getByRole("button", {
        name: "First contact reminder: replied 2026-09-11",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Wang, Cara")).getByRole("button", {
        name: "Mid-term reminder: notified by email 2026-09-18",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Wu, Dana")).getByRole("button", {
        name: "Onboarding reminder: notified manually 2026-09-07",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Chen, Alice")).getByRole("button", {
        name: "Onboarding reminder: failed on 2026-09-05",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Chen, Alice")).getByRole("button", {
        name: "Match result: not notified",
      }),
    ).toBeInTheDocument();

    // The admission email is sent by Purrf itself, and can fail on its own.
    expect(
      within(rowOf("Chen, Alice")).getByRole("button", {
        name: "Admission & onboarding: notified automatically 2026-08-27",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Hu, Ivy")).getByRole("button", {
        name: "Admission & onboarding: failed on 2026-08-29",
      }),
    ).toBeInTheDocument();

    // A dot opens that person's timeline showing emails only.
    fireEvent.click(
      within(rowOf("Wang, Cara")).getByRole("button", {
        name: "Mid-term reminder: notified by email 2026-09-18",
      }),
    );
    expect(screen.getByRole("button", { name: "Emails only" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.queryByText(/Called her/)).not.toBeInTheDocument();
  });

  it("filters to who has not had a given email, from a link", () => {
    window.history.replaceState(
      null,
      "",
      "#mentorship?email=midterm_reminder&emailState=not_sent",
    );
    render(<MentorshipAdminPrototype />);
    expect(screen.queryByRole("button", { name: "Wang, Cara" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Shen, Gina" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Ma, Erin" }),
    ).toBeInTheDocument();
  });

  it("picks a notification first, then its state, in one control", async () => {
    render(<MentorshipAdminPrototype />);
    const open = () =>
      fireEvent.keyDown(
        screen.getByRole("button", { name: "Notification filter" }),
        { key: "Enter" },
      );

    open();
    fireEvent.keyDown(
      await screen.findByRole("menuitem", { name: "Mid-term reminder" }),
      { key: "ArrowRight" },
    );
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Not notified" }),
    );

    expect(
      screen.getByRole("button", { name: "Notification filter" }),
    ).toHaveTextContent("Mid-term reminder · Not notified");
    expect(window.location.hash).toContain("email=midterm_reminder");
    expect(screen.queryByRole("button", { name: "Wang, Cara" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Ma, Erin" }),
    ).toBeInTheDocument();

    open();
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Any notification" }),
    );
    expect(
      await screen.findByRole("button", { name: "Wang, Cara" }),
    ).toBeInTheDocument();
  });
});

describe("Meetings last round", () => {
  const of = (participantId) =>
    describeLastRound(
      lastRoundOf(
        INITIAL_PARTICIPANTS.find((p) => p.participantId === participantId),
        INITIAL_PARTICIPANTS,
        INITIAL_PAIRS,
        INITIAL_ROUNDS,
      ),
    );

  it("tells the ways a last round can have gone apart", () => {
    expect(of("p-alice-7")).toBe("First time");
    expect(of("p-bob-7")).toBe("Mentorship 2025 Summer · Not matched");
    expect(of("p-fay-7")).toBe("Mentorship 2025 Summer · Withdrawn at 2/7");
    // Gina stayed; her partner left, so her pair ended early.
    expect(of("p-gina-7")).toBe("Mentorship 2025 Summer · Pair ended at 2/7");
    expect(of("p-dana-7")).toBe("Mentorship 2025 Summer · 7/7");
  });

  it("looks only at earlier rounds, by date", () => {
    // Last summer's own rows have nothing before them.
    expect(of("p-cara-6")).toBe("First time");
  });

  it("shows every pair on the person's page, from their name alone", () => {
    render(<MentorshipAdminPrototype />);
    // The partner's name in the table is plain text, not a second way in.
    expect(
      within(personRow("Liu, Bob")).queryByRole("button", { name: /Ma, Erin/ }),
    ).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Liu, Bob" }));
    // Bob carries two mentees: two sections, the first open.
    expect(
      screen.getByRole("button", { name: /with Wang, Cara/, expanded: true }),
    ).toBeInTheDocument();
    const erin = screen.getByRole("button", {
      name: /with Ma, Erin/,
      expanded: false,
    });
    fireEvent.click(erin);
    expect(screen.getByText("Ma, Erin absent")).toBeInTheDocument();
  });

  it("still opens an old pair link, on the mentee's page", () => {
    window.history.replaceState(null, "", "#mentorship/pairs/502");
    render(<MentorshipAdminPrototype />);
    expect(
      screen.getByRole("heading", { name: "Ma, Erin" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /with Liu, Bob/, expanded: true }),
    ).toBeInTheDocument();
  });

  it("offers the exemption list only until the round's matching closes", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Mentorship 2025 Summer" }),
    );
    expect(
      screen.getByRole("button", { name: "Needs exemption" }),
    ).toBeDisabled();
  });
});
