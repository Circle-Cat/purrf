import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BlockDialog from "@/pages/AdminAccounts/components/BlockDialog";
import DeactivateDialog from "@/pages/AdminAccounts/components/DeactivateDialog";
import BlockPreflight from "@/pages/AdminAccounts/components/BlockPreflight";

const holder = (userId) => ({ userId, name: `Holder ${userId}` });

const preflight = (
  applicationCount = 2,
  interviewTimes = [],
  mentorshipPairCount = 0,
  mentorshipMeetingCount = 0,
) => ({
  applicationCount,
  interviewTimes,
  mentorshipPairCount,
  mentorshipMeetingCount,
});

const account = {
  userId: 7,
  firstName: "Ada",
  lastName: "Lovelace",
  primaryEmail: "ada@circlecat.org",
};

describe("BlockDialog", () => {
  it("disables the button until a reason is typed", async () => {
    const user = userEvent.setup();
    render(<BlockDialog mode="direct" open />);

    const button = screen.getByRole("button", { name: /^Block$/ });
    expect(button).toBeDisabled();

    await user.type(screen.getByLabelText(/Reason/), "second no-show");
    expect(button).toBeEnabled();
  });

  it("requires a reviewer but not a reason in request mode", async () => {
    const user = userEvent.setup();
    render(
      <BlockDialog mode="request" open holders={[holder(9), holder(11)]} />,
    );

    expect(screen.getByLabelText("Reason (optional)")).toHaveValue("");
    expect(screen.getByRole("button", { name: /Send request/ })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText(/Reviewer/), "9");
    expect(screen.getByRole("button", { name: /Send request/ })).toBeEnabled();
  });

  it("sends a request with an empty reason when none is given", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <BlockDialog
        mode="request"
        open
        holders={[holder(9), holder(11)]}
        onConfirm={onConfirm}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/Reviewer/), "9");
    await user.click(screen.getByRole("button", { name: /Send request/ }));

    expect(onConfirm).toHaveBeenCalledWith({ reason: "", reviewerId: 9 });
  });

  it("names the account in the request title and shows the preflight above the picker", () => {
    render(
      <BlockDialog
        mode="request"
        open
        account={account}
        holders={[holder(9)]}
        preflight={preflight(1, [])}
      />,
    );

    expect(
      screen.getByText("Request a block — Ada Lovelace"),
    ).toBeInTheDocument();
    const preflightNode = screen.getByTestId("block-preflight");
    const picker = screen.getByLabelText("Reviewer");
    expect(
      preflightNode.compareDocumentPosition(picker) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("says the request goes to the named reviewer, not to whoever holds the permission", () => {
    render(<BlockDialog mode="request" open holders={[holder(9)]} />);

    expect(
      screen.getByText(
        "This does not block anyone yet. It goes to the reviewer you name below, and nothing changes for this person until they approve it. You can change the reviewer or withdraw while it waits.",
      ),
    ).toBeInTheDocument();
  });

  it("says a direct block needs no second approval", () => {
    render(<BlockDialog mode="direct" open />);

    expect(
      screen.getByText(
        "This takes effect immediately. You hold user.admin, so no second approval is required.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/Reviewer/)).not.toBeInTheDocument();
  });

  it("shows the same preflight payload in both modes", () => {
    const payload = preflight(2, ["2026-10-01T14:30:00Z"]);
    const { rerender } = render(
      <BlockDialog mode="direct" open preflight={payload} />,
    );
    const direct = screen.getByTestId("block-preflight").textContent;

    rerender(
      <BlockDialog
        mode="request"
        open
        preflight={payload}
        holders={[holder(9)]}
      />,
    );
    expect(screen.getByTestId("block-preflight").textContent).toBe(direct);
  });

  it("stays usable while the preflight is still loading", async () => {
    const user = userEvent.setup();
    render(<BlockDialog mode="direct" open preflight={null} />);

    expect(screen.getByTestId("block-preflight")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Reason/), "policy breach");
    expect(screen.getByRole("button", { name: /^Block$/ })).toBeEnabled();
  });

  it("stays usable when the preflight could not be read", async () => {
    const user = userEvent.setup();
    render(<BlockDialog mode="direct" open preflightError />);

    expect(
      screen.getByText(/Couldn't read what this will affect/),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Reason/), "policy breach");
    expect(screen.getByRole("button", { name: /^Block$/ })).toBeEnabled();
  });

  it("keeps the raiser out of the reviewer options", () => {
    render(
      <BlockDialog
        mode="request"
        open
        holders={[holder(9), holder(11)]}
        currentUserId={11}
      />,
    );

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["Select a reviewer…", "Holder 9"]);
  });

  it("says the reviewer list failed rather than blaming an empty pool", () => {
    render(<BlockDialog mode="request" open holders={[]} holdersError />);

    expect(screen.queryByLabelText(/Reviewer/)).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Couldn't load the reviewers. Close this and try again.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/No one else holds user\.admin/),
    ).not.toBeInTheDocument();
  });

  it("leaves the person being blocked out of the reviewer list", async () => {
    // The backend refuses a request whose reviewer is its target: they would
    // read their own sanction and could approve it. The picker must not offer
    // the click.
    render(
      <BlockDialog
        mode="request"
        open
        account={{ userId: 9, firstName: "Ada", lastName: "L" }}
        holders={[
          { userId: 9, name: "Ada L" },
          { userId: 11, name: "Sam Steward" },
        ]}
        currentUserId={5}
        onConfirm={() => {}}
        onOpenChange={() => {}}
      />,
    );

    const names = within(screen.getByLabelText("Reviewer"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(names).not.toContain("Ada L");
    expect(names).toContain("Sam Steward");
  });

  it("explains an empty reviewer pool and cannot be sent", () => {
    render(
      <BlockDialog
        mode="request"
        open
        holders={[holder(9)]}
        currentUserId={9}
      />,
    );

    const options = within(screen.getByLabelText("Reviewer"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(options).toEqual(["Select a reviewer…"]);
    expect(
      screen.getByText(/No one else holds user\.admin/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Send request/ })).toBeDisabled();
  });

  it("confirms a direct block with a trimmed reason and no reviewer", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <BlockDialog
        mode="direct"
        open
        account={account}
        onConfirm={onConfirm}
      />,
    );

    await user.type(screen.getByLabelText(/Reason/), "  second no-show  ");
    await user.click(screen.getByRole("button", { name: /^Block$/ }));

    expect(onConfirm).toHaveBeenCalledWith({
      reason: "second no-show",
      reviewerId: null,
    });
  });

  it("confirms a request with the picked reviewer as a number", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <BlockDialog
        mode="request"
        open
        holders={[holder(9), holder(11)]}
        onConfirm={onConfirm}
      />,
    );

    await user.type(screen.getByLabelText(/Reason/), "harassment report");
    await user.selectOptions(screen.getByLabelText(/Reviewer/), "11");
    await user.click(screen.getByRole("button", { name: /Send request/ }));

    expect(onConfirm).toHaveBeenCalledWith({
      reason: "harassment report",
      reviewerId: 11,
    });
  });

  it("clears the reason and the reviewer when it is reopened", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <BlockDialog mode="request" open holders={[holder(9)]} />,
    );

    await user.type(screen.getByLabelText(/Reason/), "typed once");
    await user.selectOptions(screen.getByLabelText(/Reviewer/), "9");

    rerender(<BlockDialog mode="request" open={false} holders={[holder(9)]} />);
    rerender(<BlockDialog mode="request" open holders={[holder(9)]} />);

    expect(screen.getByLabelText(/Reason/)).toHaveValue("");
    expect(screen.getByLabelText(/Reviewer/)).toHaveValue("");
    expect(screen.getByRole("button", { name: /Send request/ })).toBeDisabled();
  });

  it("names the account it is about to block", () => {
    render(<BlockDialog mode="direct" open account={account} />);

    expect(
      screen.getByText("Block account — Ada Lovelace"),
    ).toBeInTheDocument();
  });

  it("names a candidate the caller could only resolve to one string", () => {
    // Recruiting has no first/last pair for a candidate, only a resolved name.
    render(
      <BlockDialog
        mode="direct"
        open
        account={{ userId: 7, name: "Ada Lovelace", primaryEmail: "ada@x.com" }}
      />,
    );

    expect(
      screen.getByText("Block account — Ada Lovelace"),
    ).toBeInTheDocument();
  });
});

describe("BlockPreflight", () => {
  it("does not promise that every affected application gets closed out", () => {
    render(<BlockPreflight preflight={preflight(3, [])} />);

    expect(
      screen.getByText(
        /Tag 3 affected applications, including any already hired, and reject every one that is not already rejected/,
      ),
    ).toBeInTheDocument();
  });

  it("renders the interview dates readably", () => {
    render(
      <BlockPreflight preflight={preflight(1, ["2026-10-01T14:30:00Z"])} />,
    );

    // The zone is the runner's, so assert the shape rather than a fixed
    // instant: "Cancel 1 interview — 2026-10-01 22:30 Asia/Shanghai".
    expect(
      screen.getByText(
        /Cancel 1 interview — \d{4}-\d{2}-\d{2} \d{2}:\d{2} \S+/,
      ),
    ).toBeInTheDocument();
  });

  it("says so when nothing is scheduled", () => {
    render(<BlockPreflight preflight={preflight(0, [])} />);

    expect(
      screen.getByText("· Cancel no interviews — none are scheduled"),
    ).toBeInTheDocument();
  });

  it("keeps the irreversibility warning while the counts are still loading", () => {
    render(<BlockPreflight preflight={null} />);

    expect(
      screen.getByText(
        "· Still counting the applications, interviews and mentorship pairs this reaches",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "⚠ Unblocking later restores access, but reinstates none of the above — not the applications, not the interviews, not the mentorship pairs. Mentorship eligibility is gone for good, because it is derived from an application that this action rejects.",
      ),
    ).toBeInTheDocument();
  });

  it("says which mentorship pairs end and how many meetings go", () => {
    render(<BlockPreflight preflight={preflight(0, [], 2, 3)} />);

    expect(
      screen.getByText(
        "· End 2 mentorship pairs in rounds in progress and cancel 3 upcoming meetings; a partner left with no pair becomes unmatched",
      ),
    ).toBeInTheDocument();
  });

  it("uses the singular for one pair and one meeting", () => {
    render(<BlockPreflight preflight={preflight(0, [], 1, 1)} />);

    expect(
      screen.getByText(
        "· End 1 mentorship pair in rounds in progress and cancel 1 upcoming meeting; a partner left with no pair becomes unmatched",
      ),
    ).toBeInTheDocument();
  });

  it("says so when no pair is in a round in progress", () => {
    render(<BlockPreflight preflight={preflight(0, [])} />);

    expect(
      screen.getByText(
        "· End no mentorship pairs — none in a round in progress",
      ),
    ).toBeInTheDocument();
  });

  it("warns that unblocking does not bring the pairs back", () => {
    render(<BlockPreflight preflight={preflight(0, [])} />);

    expect(
      screen.getByText(
        "⚠ Unblocking later restores access, but reinstates none of the above — not the applications, not the interviews, not the mentorship pairs. Mentorship eligibility is gone for good, because it is derived from an application that this action rejects.",
      ),
    ).toBeInTheDocument();
  });
});

describe("DeactivateDialog", () => {
  it("deactivation carries no implication of fault and takes an optional note", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<DeactivateDialog open onConfirm={onConfirm} />);

    expect(
      screen.getByText(/no longer wants to use Purrf/i),
    ).toBeInTheDocument();
    const button = screen.getByRole("button", { name: /Deactivate/ });
    expect(button).toBeEnabled();

    await user.click(button);
    expect(onConfirm).toHaveBeenCalledWith(null);
  });

  it("spells out what deactivation does and does not touch", () => {
    render(<DeactivateDialog open account={account} onConfirm={() => {}} />);

    expect(
      screen.getByText("Deactivate account — Ada Lovelace"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "· Every page becomes inaccessible — they can still sign in",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "· Nothing is deleted; reactivating restores everything",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("· Sign-in methods and emails are left untouched"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Note — optional, kept with the record"),
    ).toBeInTheDocument();
  });

  it("passes the note through trimmed", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<DeactivateDialog open onConfirm={onConfirm} />);

    await user.type(
      screen.getByLabelText(/Note/),
      "  moved on from the program  ",
    );
    await user.click(screen.getByRole("button", { name: /Deactivate/ }));

    expect(onConfirm).toHaveBeenCalledWith("moved on from the program");
  });
});
