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

const raise = (reason) => {
  fireEvent.click(screen.getByRole("button", { name: "Raise a change" }));
  fireEvent.change(screen.getByPlaceholderText(/Five days past/), {
    target: { value: reason },
  });
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
    fireEvent.click(screen.getByRole("button", { name: "Raise a change" }));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "No reply on either channel." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));

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
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    // Alice and Dana, plus Ivy who was not selected.
    expect(screen.getAllByText("signed_up")).toHaveLength(3);

    fireEvent.click(
      within(pendingItem("Checked with Jasmine.")).getByRole("button", {
        name: "Approve",
      }),
    );
    expect(screen.getAllByText("un_matched")).toHaveLength(2);
    expect(screen.getAllByText("signed_up")).toHaveLength(1);

    // Confirmed as unmatched this time; still eligible for the next run.
    fireEvent.click(screen.getByRole("button", { name: "Matching pool" }));
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

  it("pools only people with a free slot, and exports mentors with what they have left", () => {
    render(<MentorshipAdminPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Matching pool" }));

    expect(screen.getByText("Meetings last round")).toBeInTheDocument();
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
});
