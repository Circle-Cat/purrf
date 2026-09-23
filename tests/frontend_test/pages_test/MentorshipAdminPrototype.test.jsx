import { beforeEach, describe, it, expect } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import MentorshipAdminPrototype from "@/pages/MentorshipAdminPrototype";

/** The permission chips are their own labelled group; card buttons are not. */
const chip = (name) =>
  within(screen.getByRole("group", { name: "Permissions" })).getByRole(
    "button",
    { name },
  );

/** The pair axis row, found by the label that opens it. */
const pairRow = (mentor, mentee) =>
  screen.getByRole("row", { name: `Open pair ${mentor} and ${mentee}` });

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
});

describe("MentorshipAdminPrototype smoke", () => {
  it("renders the console and walks the flows that carry the design", () => {
    render(<MentorshipAdminPrototype />);

    expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    expect(screen.getByText(/2 waiting/)).toBeInTheDocument();

    // "Meetings last round" only means something while choosing who to match.
    expect(screen.queryByText("Meetings last round")).not.toBeInTheDocument();

    // Bob carries two mentees: two rows here, one on the person axis.
    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));
    expect(screen.getAllByText("Liu, Bob")).toHaveLength(2);
    expect(screen.getByText("Mentee reminder")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Participants" }));
    fireEvent.click(screen.getByRole("button", { name: "Wang, Cara" }));
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("Participation history")).toBeInTheDocument();

    // Feedback always names whose opinion it is.
    expect(screen.getByText(/Wang, Cara's feedback about/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /With Liu, Bob/ }));
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

  it("comes back from a detail page to the same tab and filter", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));
    fireEvent.change(screen.getByPlaceholderText("Search mentor or mentee"), {
      target: { value: "Fay" },
    });
    expect(screen.queryByText("Liu, Bob")).not.toBeInTheDocument();
    expect(window.location.hash).toContain("tab=pairs");
    expect(window.location.hash).toContain("q=Fay");

    fireEvent.click(pairRow("Guo, Fay", "Shen, Gina"));
    expect(screen.getByText("Meeting log")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "← Pairs" }));
    expect(screen.getByPlaceholderText("Search mentor or mentee")).toHaveValue(
      "Fay",
    );
    expect(screen.getByText("Mentee reminder")).toBeInTheDocument();
    expect(screen.queryByText("Liu, Bob")).not.toBeInTheDocument();
  });

  it("puts a change raised from a pair on that pair's page once approved", () => {
    render(<MentorshipAdminPrototype />);

    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));
    fireEvent.click(pairRow("Liu, Bob", "Wang, Cara"));
    raise("Schedules stopped overlapping.");

    fireEvent.click(screen.getByRole("button", { name: "← Pairs" }));
    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("Liu, Bob ↔ Wang, Cara")).getByRole("button", {
        name: "Approve",
      }),
    );

    fireEvent.click(pairRow("Liu, Bob", "Wang, Cara"));
    expect(
      screen.getByText(/Schedules stopped overlapping\. — raised by/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Request a partner change — approved/),
    ).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));
    expect(
      within(pairRow("Liu, Bob", "Wang, Cara")).getByText("inactive"),
    ).toBeInTheDocument();
    expect(
      within(pairRow("Liu, Bob", "Ma, Erin")).getByText("active"),
    ).toBeInTheDocument();
  });

  it("asks for an optional note before a cell mark, and bulk marks light the cell", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));

    fireEvent.click(
      within(pairRow("Liu, Bob", "Wang, Cara")).getAllByRole("button", {
        name: "Mark",
      })[0],
    );
    expect(
      screen.getByText("First contact confirmed — Liu, Bob ↔ Wang, Cara"),
    ).toBeInTheDocument();
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Mark" }),
    );
    expect(
      within(pairRow("Liu, Bob", "Wang, Cara")).getByText("2026-09-22"),
    ).toBeInTheDocument();

    fireEvent.click(
      within(pairRow("Liu, Bob", "Ma, Erin")).getByRole("checkbox"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Mark as sent" }));
    expect(
      within(pairRow("Liu, Bob", "Ma, Erin")).getByText("2026-09-22"),
    ).toBeInTheDocument();
  });

  it("confirms a batch as unmatched through an approval, and warns about pending ones", () => {
    render(<MentorshipAdminPrototype />);

    const rowOf = (name) =>
      screen
        .getAllByRole("row")
        .find((row) => within(row).queryByRole("button", { name }));
    fireEvent.click(within(rowOf("Chen, Alice")).getByRole("checkbox"));
    fireEvent.click(within(rowOf("Wu, Dana")).getByRole("checkbox"));
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm as unmatched · 2" }),
    );

    expect(
      screen.getByText(/Already waiting on a decision/),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
      target: { value: "Checked with Jasmine." },
    });
    chooseReviewer();
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    // Alice and Dana, plus Ivy who was not selected.
    expect(screen.getAllByText("signed_up")).toHaveLength(3);

    signInAs(JASMINE);
    fireEvent.click(
      within(pendingItem("Checked with Jasmine.")).getByRole("button", {
        name: "Approve",
      }),
    );
    expect(screen.getAllByText("un_matched")).toHaveLength(2);
    expect(screen.getAllByText("signed_up")).toHaveLength(1);

    // Confirmed as unmatched this time; still eligible for the next run.
    fireEvent.click(
      screen.getByRole("button", { name: "Eligible for matching" }),
    );
    expect(screen.getAllByText("un_matched")).toHaveLength(2);
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

  it("puts a sent mid-term reminder on each timeline and stamps the mentee's cell", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));

    fireEvent.click(
      within(pairRow("Liu, Bob", "Ma, Erin")).getByRole("checkbox"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Send email · 2" }));
    fireEvent.click(screen.getByRole("button", { name: "Send 2" }));

    expect(
      within(pairRow("Liu, Bob", "Ma, Erin")).getByText("2026-09-22"),
    ).toBeInTheDocument();

    fireEvent.click(pairRow("Liu, Bob", "Ma, Erin"));
    fireEvent.click(screen.getByRole("button", { name: "← Pairs" }));
    fireEvent.click(screen.getByRole("button", { name: "Participants" }));
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
    expect(
      within(poolRow("Wu, Dana")).getByText("Not matched"),
    ).toBeInTheDocument();

    fireEvent.click(within(poolRow("Liu, Bob")).getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Export for matching · 1" }),
    ).toBeDisabled();
    fireEvent.click(within(poolRow("Chen, Alice")).getByRole("checkbox"));
    fireEvent.click(
      screen.getByRole("button", { name: "Export for matching · 2" }),
    );
    expect(
      screen.getByText(/Liu, Bob goes in with 1 slot, not 3/),
    ).toBeInTheDocument();
  });

  it("shows the existing meeting log on the pair page, editable only in a v2 round", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Pairs" }));
    fireEvent.click(pairRow("Liu, Bob", "Ma, Erin"));

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
      screen.getByText(/Revoked the No show of 2026-09-20/),
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
      screen.getByRole("button", { name: "Mark as sent" }),
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

  it("counts who has not registered against the round that is selected", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(
      screen.getByRole("button", { name: "Mentorship 2025 Summer" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));

    const rowOf = (name) =>
      screen.getAllByRole("row").find((row) => within(row).queryByText(name));
    // Registered for last summer, so not on last summer's list.
    expect(rowOf("Wang, Cara")).toBeUndefined();
    expect(rowOf("Park, Min")).toBeUndefined();
    // Took part this autumn but not last summer.
    expect(
      within(rowOf("Liu, Bob")).getByText("Mentorship 2026 Fall"),
    ).toBeInTheDocument();
    expect(rowOf("Osei, Kwame")).toBeDefined();
    // Role and onboarding come from the course rows: Dana holds both.
    expect(within(rowOf("Wu, Dana")).getAllByText("done")).toHaveLength(2);
  });

  it("lets notes be written about someone who has not registered", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));

    // In bulk, after inviting on Teams.
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Park, Min" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark as sent" }));

    fireEvent.click(screen.getByRole("button", { name: "Park, Min" }));
    expect(window.location.hash).toContain("people/3111/7");
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
});
