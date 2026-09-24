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
  historyIssuesOf,
  lastRoundOf,
} from "@/pages/MentorshipAdminPrototype/lastRound";
import {
  INITIAL_NOTES,
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

const raisePartnerChange = (pairId, reason) => {
  fireEvent.click(screen.getByRole("button", { name: "Change status / flag" }));
  fireEvent.change(screen.getByLabelText("What are you asking for"), {
    target: { value: "change_partner" },
  });
  fireEvent.change(screen.getByLabelText("Which pair"), {
    target: { value: pairId },
  });
  fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
    target: { value: reason },
  });
  chooseReviewer();
  fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
};

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
      within(personRow("Bob Liu")).getAllByRole("listitem", {
        name: /^Pair Bob Liu and/,
      }),
    ).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("Participation history")).toBeInTheDocument();

    // Feedback always names whose opinion it is. Hers is from last summer,
    // so it is under that round in the history, not in this round's block.
    expect(screen.queryByText(/Cara Wang's feedback about/)).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: /Mentorship 2025 Summer/ }),
    );
    expect(screen.getByText(/Cara Wang's feedback about/)).toBeInTheDocument();

    // Her pair is on her own page, open: no separate pair page to go to.
    expect(
      screen.getByRole("button", { name: /with Bob Liu/, expanded: true }),
    ).toBeInTheDocument();
    expect(screen.getByText("Meeting log")).toBeInTheDocument();
  });

  it("keeps feedback off the console home, behind the rounds table", () => {
    render(<MentorshipAdminPrototype />);
    expect(screen.queryByText(/^Feedback — /)).toBeNull();
  });

  describe("an exemption proved out in a later round", () => {
    const dana7 = INITIAL_PARTICIPANTS.find(
      (p) => p.participantId === "p-dana-7",
    );
    const issues = (notes, pairs = INITIAL_PAIRS) =>
      historyIssuesOf(
        dana7,
        INITIAL_PARTICIPANTS,
        pairs,
        INITIAL_ROUNDS,
        notes,
        new Set(),
      );
    const note = (noteId, roundId, tag) => ({
      noteId,
      userId: 3104,
      roundId,
      pairId: null,
      tag,
      body: "",
      authorId: 2002,
      createdAt: "2025-06-01",
    });

    it("clears the red flag it covered", () => {
      // Red-flagged in 2024 Fall, exempted for 2025 Summer, 7/7 there.
      expect(issues(INITIAL_NOTES)).toEqual([]);
    });

    it("does not clear it without the exemption", () => {
      expect(
        issues(INITIAL_NOTES.filter((n) => n.tag !== "matching_exemption")),
      ).toEqual(["Red flag in Mentorship 2024 Fall"]);
    });

    it("does not clear it when the exempted round went wrong again", () => {
      expect(issues([...INITIAL_NOTES, note("n-x", 6, "no_show")])).toEqual([
        "Red flag in Mentorship 2024 Fall",
        "No show in Mentorship 2025 Summer",
      ]);
      expect(issues([...INITIAL_NOTES, note("n-y", 6, "red_flag")])).toEqual([
        "Red flag in Mentorship 2024 Fall",
        "Red flag in Mentorship 2025 Summer",
      ]);
    });

    it("does not clear a red flag from after the exempted round", () => {
      // Proved out in 2025 Summer; a new flag in 2026 Fall still counts.
      const later = { ...dana7, roundId: 8 };
      const rounds = [
        ...INITIAL_ROUNDS,
        {
          id: 8,
          name: "Mentorship 2027 Spring",
          timeline: { meetingsCompletionDeadlineAt: "2027-05-31" },
        },
      ];
      expect(
        historyIssuesOf(
          later,
          INITIAL_PARTICIPANTS,
          INITIAL_PAIRS,
          rounds,
          [...INITIAL_NOTES, note("n-z", 7, "red_flag")],
          new Set(),
        ),
      ).toContain("Red flag in Mentorship 2026 Fall");
    });

    it("does not clear it for an exempted round they were never matched in", () => {
      expect(
        issues(
          INITIAL_NOTES,
          INITIAL_PAIRS.filter((p) => p.pairId !== 490),
        ),
      ).toEqual(["Red flag in Mentorship 2024 Fall"]);
    });
  });

  it("keeps the old flag on the record, with the exemption beside it", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Dana Wu" }));
    const rowOf = (name) =>
      screen.getByRole("button", { name: new RegExp(name) }).closest("li");
    expect(
      within(rowOf("Mentorship 2024 Fall")).getByText(/Red flag/),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Mentorship 2025 Summer")).getByText("Exempted"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Needs an exemption before being matched this round"),
    ).toBeNull();
  });

  it("shows the user id beside every name, and finds a person by it exactly", () => {
    render(<MentorshipAdminPrototype />);
    const dana = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Dana Wu" }));
    expect(within(dana).getByText(/^ID 3104 · /)).toBeInTheDocument();

    const search = screen.getByPlaceholderText("Search name, email or ID");
    fireEvent.change(search, { target: { value: "3104" } });
    const names = () =>
      screen
        .getAllByRole("row")
        .map((r) => within(r).queryAllByRole("button")[0]?.textContent)
        .filter((n) => n && n !== "Round Name");
    expect(screen.getByRole("button", { name: "Dana Wu" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Alice Chen" })).toBeNull();
    // A part of an id is not a match: 310 would otherwise find everyone.
    fireEvent.change(search, { target: { value: "310" } });
    expect(screen.queryByRole("button", { name: "Dana Wu" })).toBeNull();
    expect(names()).not.toContain("Alice Chen");

    fireEvent.click(screen.getByRole("button", { name: /^Not registered/ }));
    fireEvent.change(search, { target: { value: "3108" } });
    expect(
      screen.getByRole("button", { name: "Kwame Osei" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Min Park" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Kwame Osei" }));
    expect(screen.getByText(/^ID 3108 · /)).toBeInTheDocument();
  });

  it("applies Role on the not-registered list, by admitted role", () => {
    window.history.replaceState(
      null,
      "",
      "#mentorship?filter=unregistered&role=mentor",
    );
    render(<MentorshipAdminPrototype />);
    // Min took part as a mentor; Lia was admitted as both.
    expect(
      screen.getByRole("button", { name: "Min Park" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Lia Rossi" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kwame Osei" })).toBeNull();
  });

  it("says so when a feedback link names no round", () => {
    window.history.replaceState(null, "", "#mentorship/feedback/99");
    render(<MentorshipAdminPrototype />);
    expect(screen.getByText("No such round.")).toBeInTheDocument();
    expect(screen.queryByText(/^Feedback — /)).toBeNull();
  });

  it("orders the three filters the way a person moves through them", () => {
    render(<MentorshipAdminPrototype />);
    const labels = [
      "Not registered for this round",
      /^Needs exemption/,
      "Eligible for matching",
    ].map((name) => screen.getByRole("button", { name }));
    labels.reduce((prev, next) => {
      expect(
        prev.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
      return next;
    });
  });

  it("lays the rounds table out as main does, with a feedback column", () => {
    render(<MentorshipAdminPrototype />);
    const table = screen
      .getByRole("button", { name: "Mentorship 2025 Summer" })
      .closest("table");
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual([
      "Round Name",
      "Participants",
      "Required Meetings",
      "Mentor Rating",
      "Mentee Rating",
      "Average Meetings Per Pair",
      "Feedback",
      "Action",
    ]);
    const summer = within(table)
      .getByRole("button", { name: "Mentorship 2025 Summer" })
      .closest("tr");
    // Dana (mentor) rated 5 and Cara (mentee) 4; two more owe theirs.
    expect(within(summer).getByText("5.00")).toBeInTheDocument();
    expect(within(summer).getByText("4.00")).toBeInTheDocument();
    expect(within(summer).getByText("2 of 4 sent")).toBeInTheDocument();
    expect(screen.getByText(/^Total Completed Rounds: 2$/)).toBeInTheDocument();

    fireEvent.click(
      within(summer).getByRole("button", {
        name: "Feedback for Mentorship 2025 Summer",
      }),
    );
    expect(window.location.hash).toContain("feedback/6");
    expect(
      screen.getByRole("heading", {
        name: "Feedback — Mentorship 2025 Summer",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Cara Wang's feedback about Dana Wu:", { exact: false }),
    ).toBeInTheDocument();

    // Who still owes it, in one click.
    fireEvent.click(screen.getByLabelText("Not sent only"));
    expect(screen.queryByRole("button", { name: "Cara Wang" })).toBeNull();
    expect(screen.getAllByText("Not sent").length).toBeGreaterThan(0);

    // A name opens that person's page on that round.
    fireEvent.click(
      screen
        .getAllByRole("button", { name: /\w+ \w+/ })
        .find((b) => b.closest("tbody")),
    );
    expect(window.location.hash).toContain("round=6");
  });

  it("hides the feedback column, and opens rounds read-only, without the grants", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(chip("Feedback"));
    expect(screen.queryByRole("columnheader", { name: "Feedback" })).toBeNull();
    fireEvent.click(chip("Write"));
    fireEvent.click(
      screen.getByRole("button", { name: "View Mentorship 2026 Fall" }),
    );
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("View round")).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Save" })).toBeNull();
    // Read-only means the fields too, not just a missing button.
    expect(within(dialog).getAllByRole("textbox")[0]).toBeDisabled();
  });

  it("drops whole blocks rather than greying them out when a grant is missing", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(chip("Approve"));
    expect(screen.queryByText("Pending approvals")).not.toBeInTheDocument();

    fireEvent.click(chip("Feedback"));
    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Mentorship 2025 Summer/ }),
    );
    expect(screen.getByText("Meeting log — with Dana Wu")).toBeInTheDocument();
    expect(screen.queryByText(/feedback about/)).not.toBeInTheDocument();
  });

  it("raises a request instead of writing the note directly", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(screen.getByRole("button", { name: "Dana Wu" }));
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

    fireEvent.change(screen.getByPlaceholderText("Search name, email or ID"), {
      target: { value: "Bob" },
    });
    expect(screen.queryByRole("button", { name: "Cara Wang" })).toBeNull();
    expect(window.location.hash).toContain("q=Bob");

    fireEvent.click(screen.getByRole("button", { name: "Bob Liu" }));
    expect(screen.getByText("Meeting log")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    expect(screen.getByPlaceholderText("Search name, email or ID")).toHaveValue(
      "Bob",
    );
    expect(screen.queryByRole("button", { name: "Cara Wang" })).toBeNull();
  });

  it("ends the pair on an approved partner change, and records it on the person", () => {
    render(<MentorshipAdminPrototype />);

    // One way in: Bob's name. His pairs are all on his page.
    fireEvent.click(screen.getByRole("button", { name: "Bob Liu" }));
    raisePartnerChange("501", "Schedules stopped overlapping.");

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("Bob Liu ↔ Cara Wang")).getByRole("button", {
        name: "Approve",
      }),
    );

    // Approving it ends the pair: Cara has a free slot again and can be
    // matched with someone else.
    expect(within(pairLine("Bob Liu", "Cara Wang")).getByText("Ended"));
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(personRow("Cara Wang")).toBeDefined();
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Bob Liu" }));
    // A badge beside his status, and the details on his timeline; the pair's
    // section holds only its meeting log.
    // Once beside his status, once as the timeline entry's tag.
    expect(screen.getAllByText("Partner change request")).toHaveLength(2);
    expect(
      screen.getByText(/Schedules stopped overlapping\. — raised by/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /with Cara Wang/ }));
    expect(screen.getAllByText("Meeting log")).toHaveLength(2);
    expect(screen.queryByText("Notes about this pair")).toBeNull();
    expect(screen.queryByText("Status history")).toBeNull();
  });

  it("raises a partner change from the same dialog, on a pair still going", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Bob Liu" }));
    expect(
      screen.queryByRole("button", { name: /^Change partner/ }),
    ).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: "Change status / flag" }),
    );
    fireEvent.change(screen.getByLabelText("What are you asking for"), {
      target: { value: "change_partner" },
    });
    const pair = screen.getByLabelText("Which pair");
    // Bob has two pairs going, so he has to say which.
    expect(pair).toHaveValue("none");
    expect(
      screen.getByRole("button", { name: "Send for approval" }),
    ).toBeDisabled();
    expect(
      within(pair)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Choose a pair…", "Bob Liu ↔ Cara Wang", "Bob Liu ↔ Erin Ma"]);
  });

  it("shows a partner change raised from the mentor's page on the mentor's page too", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Bob Liu" }));
    raisePartnerChange("501", "Schedules stopped overlapping.");

    // Listed with Erin's request on Bob's other pair; only his own can be
    // withdrawn by him.
    expect(
      screen.getByText(/Request a partner change \(Bob Liu ↔ Cara Wang\)/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    expect(
      screen.queryByText(/Request a partner change \(Bob Liu ↔ Cara Wang\)/),
    ).toBeNull();
  });

  it("ends the person's pair when a withdrawal is approved", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
    raise("She has left the programme.");
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("She has left the programme.")).getByRole("button", {
        name: "Approve",
      }),
    );

    // Her pair has ended: still listed, marked Ended, nothing left to mark.
    const ended = pairLine("Bob Liu", "Cara Wang");
    expect(within(ended).getByText("Ended")).toBeInTheDocument();
    expect(within(ended).queryByRole("button")).toBeNull();
    expect(
      within(pairLine("Bob Liu", "Erin Ma")).queryByText("Ended"),
    ).toBeNull();
  });

  it("asks for an optional note before marking first contact, and marks a notification on the person's page", () => {
    render(<MentorshipAdminPrototype />);

    // First contact sits on the mentee's row: it is the mentee who reaches out.
    fireEvent.click(
      within(personRow("Cara Wang")).getByRole("button", {
        name: "Mark first contact — Cara Wang",
      }),
    );
    expect(
      screen.getByText("First contact confirmed — Bob Liu ↔ Cara Wang"),
    ).toBeInTheDocument();
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Mark" }),
    );
    expect(
      within(personRow("Cara Wang")).getByRole("button", {
        name: "First contact confirmed 2026-09-22 — Cara Wang",
      }),
    ).toBeInTheDocument();
    // The mentor's row has no such mark.
    expect(
      within(personRow("Bob Liu")).queryByRole("button", {
        name: /^(Mark first contact|First contact confirmed)/,
      }),
    ).toBeNull();

    // The list can send email to many at once, but marking one sent some
    // other way happens on the person's page, with a note of how.
    fireEvent.click(within(personRow("Erin Ma")).getByRole("checkbox"));
    expect(
      screen.queryByRole("button", { name: "Mark as notified" }),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Erin Ma" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark as notified" }));
    const dialog = screen.getByRole("dialog");
    const confirm = within(dialog).getByRole("button", {
      name: "Mark as notified",
    });
    fireEvent.change(within(dialog).getByLabelText("Which notification"), {
      target: { value: "midterm_reminder" },
    });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByPlaceholderText(/Sent on Teams/), {
      target: { value: "Sent on Teams on 9/22." },
    });
    fireEvent.click(confirm);
    expect(screen.getByText("Sent on Teams on 9/22.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    expect(
      within(personRow("Erin Ma")).getByRole("button", {
        name: "Mid-term reminder: notified manually 2026-09-22",
      }),
    ).toBeInTheDocument();
  });

  it("blocks someone from their page through an approval, ending their pairs", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Erin Ma" }));
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
      within(personRow("Erin Ma")).getByText("Blocked"),
    ).toBeInTheDocument();
    expect(
      within(pairLine("Bob Liu", "Erin Ma")).getByText("Ended"),
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
    fireEvent.click(within(personRow("Alice Chen")).getByRole("checkbox"));
    expect(
      screen.queryByRole("button", { name: /Confirm as unmatched/ }),
    ).toBeNull();
  });

  it("does not apply an approval the world has moved past, and says why", () => {
    render(<MentorshipAdminPrototype />);
    // Dana has a no show waiting; she withdraws before anyone decides it.
    fireEvent.click(screen.getByRole("button", { name: "Dana Wu" }));
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
        name: "Not applied: Mark as no show — Dana Wu",
      }),
    ).toHaveTextContent("Dana Wu has already withdrawn.");
    fireEvent.click(screen.getByRole("button", { name: "Dana Wu" }));
    expect(screen.getByText("Not applied")).toBeInTheDocument();
    expect(screen.queryByText("No show")).toBeNull();
  });

  it("lists only earlier rounds under participation history", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
    const history = screen
      .getByText("Participation history")
      .closest("section");
    expect(
      within(history).getByRole("button", { name: /Mentorship 2025 Summer/ }),
    ).toBeInTheDocument();
    expect(within(history).queryByText(/Mentorship 2026 Fall/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    fireEvent.click(screen.getByRole("button", { name: "Alice Chen" }));
    expect(screen.getByText(/No earlier rounds/)).toBeInTheDocument();
  });

  it("opens an earlier round in place, with its flags, read only", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Wei Tan" }));
    const history = screen
      .getByText("Participation history")
      .closest("section");
    // Never paired last summer, but the round still opens, and its red flag
    // shows on the row.
    expect(within(history).getByText("Red flag")).toBeInTheDocument();
    fireEvent.click(
      within(history).getByRole("button", { name: /Mentorship 2025 Summer/ }),
    );
    // The page stays where it is; the round opens under its row.
    expect(window.location.hash).not.toContain("round=6");
    expect(
      within(history).getByRole("button", {
        name: /Mentorship 2025 Summer/,
        expanded: true,
      }),
    ).toBeInTheDocument();
    expect(
      within(history).getByText(/Missed two agreed calls/),
    ).toBeInTheDocument();
    expect(
      within(history).queryByRole("button", { name: "Revoke" }),
    ).toBeNull();
  });

  it("shows an earlier round's meeting log inside its history row", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
    const history = screen
      .getByText("Participation history")
      .closest("section");
    fireEvent.click(
      within(history).getByRole("button", { name: /Mentorship 2025 Summer/ }),
    );
    expect(
      within(history).getByText("Meeting log — with Dana Wu"),
    ).toBeInTheDocument();
    expect(within(history).queryByRole("button", { name: "Edit" })).toBeNull();
  });

  it("shows a failed send as failed on the timeline, not as sent", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Alice Chen" }));
    expect(screen.getByText("Failed to send")).toBeInTheDocument();
    expect(screen.queryByText("Email sent")).toBeNull();
  });

  it("keeps emails and notes on one timeline, and Refresh pulls replies in", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));

    expect(screen.getAllByText("Email sent").length).toBeGreaterThan(0);
    expect(screen.getByText("Reply")).toBeInTheDocument();
    expect(screen.getByText(/Called her/)).toBeInTheDocument();

    // One list, newest first, whatever the kind: the call on 9/12 sits
    // between the email of 9/10 and the reminder of 9/18.
    const entries = screen
      .getAllByText(/Called her|Our records show|You have logged 0 of 5/)
      .map((el) => el.textContent);
    expect(entries.map((e) => e.slice(0, 10))).toEqual([
      "You have l",
      "Called her",
      "Our record",
    ]);

    expect(screen.queryByText(/we met twice/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh emails" }));
    expect(screen.getByText(/1 new reply/)).toBeInTheDocument();
    expect(screen.getByText(/we met twice/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Refresh emails" }));
    expect(screen.getByText(/no new replies/)).toBeInTheDocument();
  });

  it("puts a sent mid-term reminder on the timeline and in the Notifications column", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(within(personRow("Erin Ma")).getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Send email · 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Send 1" }));

    expect(
      within(personRow("Erin Ma")).getByRole("button", {
        name: "Mid-term reminder: notified by email 2026-09-22",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Erin Ma" }));
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
    expect(poolRow("Cara Wang")).toBeUndefined();
    expect(poolRow("Erin Ma")).toBeUndefined();
    // Onboarding not done.
    expect(poolRow("Ivy Hu")).toBeUndefined();
    // Matched, but a slot is still open.
    expect(within(poolRow("Bob Liu")).getByText("1 of 3")).toBeInTheDocument();
    expect(within(poolRow("Fay Guo")).getByText("2 of 2")).toBeInTheDocument();
    // The four states still read as four answers here.
    expect(
      within(poolRow("Alice Chen")).getByText("First time"),
    ).toBeInTheDocument();
    // Their latest earlier round, told apart rather than turned into a 0.
    expect(
      within(poolRow("Dana Wu")).getByText("Mentorship 2025 Summer · 7/7"),
    ).toBeInTheDocument();
    expect(
      within(poolRow("Bob Liu")).getByText(
        "Mentorship 2025 Summer · Not matched",
      ),
    ).toBeInTheDocument();
    expect(
      within(poolRow("Fay Guo")).getByText(
        "Mentorship 2025 Summer · Withdrawn at 2/7",
      ),
    ).toBeInTheDocument();

    fireEvent.click(within(poolRow("Bob Liu")).getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Run matching · 1" }),
    ).toBeDisabled();
    fireEvent.click(within(poolRow("Alice Chen")).getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Run matching · 2" }),
    ).toBeEnabled();
  });

  it("shows the existing meeting log on the pair page, editable only in a v2 round", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Erin Ma" }));

    expect(screen.getByText("Erin Ma absent")).toBeInTheDocument();
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
      expect(screen.queryByText("Erin Ma absent")).not.toBeInTheDocument(),
    );
  });

  it("leaves a v1 round's meeting log read-only", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Mentorship 2025 Summer/ }),
    );
    expect(screen.getByText("Meeting log — with Dana Wu")).toBeInTheDocument();
  });

  it("sends a request to a named reviewer, and never lets the raiser decide it", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Dana Wu" }));
    raise("Still no reply.");
    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));

    const mine = pendingItem("Still no reply.");
    expect(within(mine).getByText(/You raised this/)).toBeInTheDocument();
    expect(within(mine).queryByRole("button", { name: "Approve" })).toBeNull();
    expect(
      within(mine).getByText(/Sent\s+to\s+Jasmine Wang/),
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
    fireEvent.click(screen.getByRole("button", { name: "Dana Wu" }));
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
          within(row).queryByRole("button", { name: "Cara Wang" }),
        );
    expect(within(caraRow()).getByText("No show")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
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

    fireEvent.click(screen.getByRole("button", { name: "Cara Wang" }));
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
    expect(screen.queryByRole("button", { name: "Cara Wang" })).toBeNull();

    fireEvent.click(filter);
    expect(screen.queryByText("Free slots")).not.toBeInTheDocument();
    expect(screen.queryByText("Meetings last round")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cara Wang" }),
    ).toBeInTheDocument();
  });

  it("finds who has not registered this round, and invites them to the new one", () => {
    render(<MentorshipAdminPrototype />);
    expect(
      screen.queryByRole("button", { name: "Non-participants" }),
    ).not.toBeInTheDocument();

    // No count-and-link above the table: the filter is the one way in.
    expect(screen.queryByText(/have not registered for/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Show them" })).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: "Not registered for this round" }),
    );
    expect(window.location.hash).toContain("filter=unregistered");

    // Took part last summer, not signed up again: exactly who an invitation is for.
    const minRow = screen
      .getAllByRole("row")
      .find((row) => within(row).queryByText("Min Park"));
    expect(
      within(minRow).getByText("Mentorship 2025 Summer"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Never")).toHaveLength(2);
    // Handed an onboarding course but never admitted: not in the programme.
    expect(screen.queryByText("Tao Zhou")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select Kwame Osei" }),
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Min Park" }));
    expect(
      screen.queryByRole("button", { name: "Mark as notified" }),
    ).toBeNull();
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
    fireEvent.click(
      screen.getByRole("button", { name: "Not registered for this round" }),
    );
    const rowOf = (name) =>
      screen.getAllByRole("row").find((row) => within(row).queryByText(name));
    // Took part last summer and not this autumn.
    expect(
      within(rowOf("Min Park")).getByText("Mentorship 2025 Summer"),
    ).toBeInTheDocument();
    // Registered this autumn, so not on the list.
    expect(rowOf("Alice Chen")).toBeUndefined();
    // Training comes from the course rows; the role from the admission.
    const kwame = rowOf("Kwame Osei");
    expect(within(kwame).getByText("In progress")).toBeInTheDocument();
    expect(within(kwame).getByText("mentee")).toBeInTheDocument();
    // Counted from registrations: one earlier round for Min, none for Kwame.
    const cells = (row) =>
      within(row)
        .getAllByRole("cell")
        .map((c) => c.textContent);
    const roundsColumn = within(kwame.closest("table"))
      .getAllByRole("columnheader")
      .findIndex((h) => h.textContent === "Rounds taken part");
    expect(cells(rowOf("Min Park"))[roundsColumn]).toBe("1");
    expect(cells(kwame)[roundsColumn]).toBe("0");
    // Admitted twice: still one row, so one email; a line per role.
    const lia = screen
      .getAllByRole("row")
      .filter((row) => within(row).queryByText("Lia Rossi"));
    expect(lia).toHaveLength(1);
    const liaCells = within(lia[0]).getAllByRole("cell");
    const lines = (cell) =>
      [...cell.querySelectorAll("div")].map((d) => d.textContent);
    expect(lines(liaCells[2])).toEqual(["mentor", "mentee"]);
    expect(lines(liaCells[3])).toEqual(["Done", "Not started"]);
    // Taking part is the person's, not the role's: one value, not a line each.
    expect(liaCells[7].textContent).toBe("0");
    expect(liaCells[8].textContent).toBe("Never");

    // A finished round has nobody left to invite: the filter is off, and
    // switching to it drops the list.
    fireEvent.click(
      screen.getByRole("button", { name: "Mentorship 2025 Summer" }),
    );
    expect(
      screen.getByRole("button", { name: "Not registered for this round" }),
    ).toBeDisabled();
    expect(rowOf("Kwame Osei")).toBeUndefined();
  });

  it("lets notes be written about someone who has not registered", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Not registered for this round" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Min Park" }));
    expect(window.location.hash).toContain("participants/3111?round=7");
    expect(
      screen.getByText(/Not registered for this round/),
    ).toBeInTheDocument();

    // Invited on Teams: marked from his page, with how it went out.
    fireEvent.click(screen.getByRole("button", { name: "Mark as notified" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Which notification"), {
      target: { value: "round_invitation" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText(/Sent on Teams/), {
      target: { value: "Invited on Teams." },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Mark as notified" }),
    );
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
    expect(
      screen.getByRole("button", { name: /Mentorship 2025 Summer/ }),
    ).toBeInTheDocument();
  });

  it("shows each person's account state beside their round status", () => {
    render(<MentorshipAdminPrototype />);
    expect(screen.getByText("Account")).toBeInTheDocument();
    const rowOf = (name) =>
      screen.getAllByRole("row").find((row) => within(row).queryByText(name));

    expect(within(rowOf("Bob Liu")).getByText("Active")).toBeInTheDocument();
    expect(within(rowOf("Gina Shen")).getByText("Blocked")).toBeInTheDocument();
    expect(within(rowOf("Gina Shen")).queryByText("Active")).toBeNull();
    expect(
      within(rowOf("Ivy Hu")).getByText("Deactivated"),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Not registered for this round" }),
    );
    // Independent flags: both at once.
    expect(
      within(rowOf("Lia Rossi")).getByText("Deactivated"),
    ).toBeInTheDocument();
    expect(within(rowOf("Lia Rossi")).getByText("Blocked")).toBeInTheDocument();
  });

  it("never offers a blocked person to matching", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(screen.queryByRole("button", { name: "Oscar Lin" })).toBeNull();
    // Gina and Oscar blocked, Ivy deactivated.
    expect(screen.getByText(/3 blocked or/)).toBeInTheDocument();
  });

  it("keeps people with a past to look at out of matching until an exemption is approved", () => {
    render(<MentorshipAdminPrototype />);
    // The pool itself is clean: nobody waiting on an exemption is in it.
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(screen.queryByRole("button", { name: "Sora Kim" })).toBeNull();
    expect(screen.getByText(/2 waiting on an exemption/)).toBeInTheDocument();

    // Counted on the button without asking; listed when pressed.
    fireEvent.click(
      screen.getByRole("button", { name: "Needs exemption · 2" }),
    );
    expect(
      within(personRow("Sora Kim")).getByText(
        "Met 3/7 in Mentorship 2025 Summer",
      ),
    ).toBeInTheDocument();
    expect(
      within(personRow("Wei Tan")).getByText(
        "Red flag in Mentorship 2025 Summer",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Sora Kim" }));
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
    expect(personRow("Sora Kim")).toBeUndefined();
    expect(
      screen.getByRole("button", { name: "Needs exemption · 1" }),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(personRow("Sora Kim")).toBeDefined();
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
    ["Bob Liu", "Fay Guo", "Alice Chen", "Dana Wu"].forEach((name) =>
      fireEvent.click(within(row(name)).getByRole("checkbox")),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run matching · 4" }));
  };

  it("offers only a matching run, not an email, from the matching pool", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    const row = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Bob Liu" }));
    fireEvent.click(within(row).getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Run matching · 1" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Send email/ })).toBeNull();
  });

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
      .find((r) => within(r).queryByRole("button", { name: "Alice Chen" }));
    fireEvent.click(within(row).getByRole("checkbox"));
    const bob = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Bob Liu" }));
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

    fireEvent.click(screen.getByRole("button", { name: /^Alice Chen/ }));
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
    fireEvent.click(screen.getByRole("button", { name: /^Dana Wu/ }));
    fireEvent.change(screen.getByLabelText("Mentor for Dana Wu"), {
      target: { value: "3102" },
    });
    expect(
      screen.getByText(/Bob Liu is given 2 mentees but has 1 slot left/),
    ).toBeInTheDocument();
    // Moving her cleared the reason written for her old mentor.
    expect(
      screen.getByText(/Dana Wu is matched with no reason/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request publishing" }),
    ).toBeDisabled();

    // Send Alice to Fay instead and write both reasons.
    fireEvent.change(screen.getByLabelText("Mentor for Alice Chen"), {
      target: { value: "3106" },
    });
    fireEvent.change(screen.getByLabelText("Reason for Alice Chen"), {
      target: { value: "Fay hires for ML-adjacent roles." },
    });
    fireEvent.change(screen.getByLabelText("Reason for Dana Wu"), {
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
    expect(screen.getByLabelText("Mentor for Alice Chen")).toBeDisabled();

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
    expect(pairLine("Fay Guo", "Alice Chen")).toBeInTheDocument();
    expect(pairLine("Bob Liu", "Dana Wu")).toBeInTheDocument();
  });

  it("keeps the reason within what the published column can hold", () => {
    render(<MentorshipAdminPrototype />);
    startRun();
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Alice Chen/ }));
    fireEvent.change(screen.getByLabelText("Reason for Alice Chen"), {
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

    fireEvent.click(screen.getByRole("button", { name: /^Alice Chen/ }));
    fireEvent.change(screen.getByLabelText("Reason for Alice Chen"), {
      target: { value: "A different reason." },
    });
    expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Request publishing" }),
    ).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(screen.queryByText(/Unsaved changes/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Reason for Alice Chen")).not.toHaveValue(
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
    ["Bob Liu", "Fay Guo", "Dana Wu"].forEach((name) =>
      fireEvent.click(within(personRow(name)).getByRole("checkbox")),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run matching · 3" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    expect(screen.getByText(/Without a partner: Bob Liu/)).toBeInTheDocument();
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
      /1 unmatched: Bob Liu/,
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
      within(personRow("Bob Liu")).getByText("matched"),
    ).toBeInTheDocument();
    expect(pairLine("Fay Guo", "Dana Wu")).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: "Alice Chen" }));
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
    ).toHaveTextContent("Alice Chen has withdrawn or been closed out.");
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(within(personRow("Alice Chen")).getByText("withdrawn"));
    expect(
      screen.queryAllByRole("listitem", { name: /^Pair .* and Alice Chen$/ }),
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
    expect(pairLines("Bob Liu", "Alice Chen")).toHaveLength(0);
  });

  it("puts a latecomer through a supplemental run, approved like the first", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    ["Fay Guo", "Alice Chen"].forEach((name) =>
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

    // Dana joins late; Bob has agreed to take her. The same filter, a run
    // with just them, the agreed reason, and an approval.
    const eligible = screen.getByRole("button", {
      name: "Eligible for matching",
    });
    if (eligible.getAttribute("aria-pressed") !== "true") {
      fireEvent.click(eligible);
    }
    ["Bob Liu", "Dana Wu"].forEach((name) =>
      fireEvent.click(within(personRow(name)).getByRole("checkbox")),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run matching · 2" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate the run finishing/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Dana Wu/ }));
    fireEvent.change(screen.getByLabelText("Reason for Dana Wu"), {
      target: { value: "Bob offered on Teams, 9/22." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    fireEvent.click(screen.getByRole("button", { name: "Request publishing" }));
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Late joiner; Bob agreed." },
    });
    chooseReviewer("2001");
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    expect(
      screen.getByText(/Waiting for approval to publish/),
    ).toBeInTheDocument();
    expect(screen.getByText("Earlier published runs")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "← Participants" }));
    signInAs("2001");
    fireEvent.click(
      within(pendingItem("Late joiner; Bob agreed.")).getByRole("button", {
        name: "Approve",
      }),
    );
    expect(screen.queryByText(/^Not applied/)).toBeNull();
    // Both are full now, so they have left the eligible list.
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(pairLine("Bob Liu", "Dana Wu")).toBeInTheDocument();
  });

  it("shows where each person's emails stand, one dot per email of the round", () => {
    render(<MentorshipAdminPrototype />);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    // How far each person has got, in words, above the dots.
    const cara = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Cara Wang" }));
    expect(
      within(cara).getByText("Mid-term reminder · 2026-09-18"),
    ).toBeInTheDocument();
    const alice = screen
      .getAllByRole("row")
      .find((r) => within(r).queryByRole("button", { name: "Alice Chen" }));
    expect(within(alice).getByText("Failed")).toBeInTheDocument();
    const rowOf = (name) =>
      screen
        .getAllByRole("row")
        .find((r) => within(r).queryByRole("button", { name }));

    // Replied, notified by email, notified manually, failed, not notified.
    expect(
      within(rowOf("Cara Wang")).getByRole("button", {
        name: "First contact reminder: replied 2026-09-11",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Cara Wang")).getByRole("button", {
        name: "Mid-term reminder: notified by email 2026-09-18",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Dana Wu")).getByRole("button", {
        name: "Onboarding reminder: notified manually 2026-09-07",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Alice Chen")).getByRole("button", {
        name: "Onboarding reminder: failed on 2026-09-05",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Alice Chen")).getByRole("button", {
        name: "Match result: not notified",
      }),
    ).toBeInTheDocument();

    // The admission email is sent by Purrf itself, and can fail on its own.
    expect(
      within(rowOf("Alice Chen")).getByRole("button", {
        name: "Admission & onboarding: notified automatically 2026-08-27",
      }),
    ).toBeInTheDocument();
    expect(
      within(rowOf("Ivy Hu")).getByRole("button", {
        name: "Admission & onboarding: failed on 2026-08-29",
      }),
    ).toBeInTheDocument();

    // A line opens that person's page.
    fireEvent.click(
      within(rowOf("Cara Wang")).getByRole("button", {
        name: "Mid-term reminder: notified by email 2026-09-18",
      }),
    );
    expect(
      screen.getByRole("heading", { name: "Cara Wang" }),
    ).toBeInTheDocument();
  });

  it("filters to who has not had a given email, from a link", () => {
    window.history.replaceState(
      null,
      "",
      "#mentorship?email=midterm_reminder&emailState=not_sent",
    );
    render(<MentorshipAdminPrototype />);
    expect(screen.queryByRole("button", { name: "Cara Wang" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Gina Shen" })).toBeNull();
    expect(screen.getByRole("button", { name: "Erin Ma" })).toBeInTheDocument();
  });

  it("filters by account state, from a link", () => {
    window.history.replaceState(null, "", "#mentorship?account=deactivated");
    render(<MentorshipAdminPrototype />);
    expect(screen.getByRole("button", { name: "Ivy Hu" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Alice Chen" })).toBeNull();
  });

  it("filters the not-registered list by account state too", () => {
    window.history.replaceState(
      null,
      "",
      "#mentorship?filter=unregistered&account=blocked",
    );
    render(<MentorshipAdminPrototype />);
    // Blocked and deactivated at once: she counts as blocked.
    expect(
      screen.getByRole("button", { name: "Lia Rossi" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kwame Osei" })).toBeNull();
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
    expect(screen.queryByRole("button", { name: "Cara Wang" })).toBeNull();
    expect(screen.getByRole("button", { name: "Erin Ma" })).toBeInTheDocument();

    open();
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Any notification" }),
    );
    expect(
      await screen.findByRole("button", { name: "Cara Wang" }),
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
      within(personRow("Bob Liu")).queryByRole("button", { name: /Erin Ma/ }),
    ).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Bob Liu" }));
    // Bob carries two mentees: two sections, the first open.
    expect(
      screen.getByRole("button", { name: /with Cara Wang/, expanded: true }),
    ).toBeInTheDocument();
    const erin = screen.getByRole("button", {
      name: /with Erin Ma/,
      expanded: false,
    });
    fireEvent.click(erin);
    expect(screen.getByText("Erin Ma absent")).toBeInTheDocument();
  });

  it("still opens an old pair link, on the mentee's page", () => {
    window.history.replaceState(null, "", "#mentorship/pairs/502");
    render(<MentorshipAdminPrototype />);
    expect(
      screen.getByRole("heading", { name: "Erin Ma" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /with Bob Liu/, expanded: true }),
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

  it("offers matching only while the round is running", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Mentorship 2025 Summer" }),
    );
    const eligible = screen.getByRole("button", {
      name: "Eligible for matching",
    });
    expect(eligible).toBeDisabled();
    expect(eligible).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByText("Free slots")).toBeNull();
  });
});
