import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import BlockFromPurrf from "@/pages/MentorshipManagement/components/BlockFromPurrf";
import {
  createBlockRequest,
  getBlockPreflight,
  getRaisedBlockRequests,
  getUserAdmins,
  reassignBlockRequest,
  withdrawBlockRequest,
} from "@/api/adminAccountsApi";
import { useAuth } from "@/context/auth";
import { detailOf } from "../participantDetail.helper";

vi.mock("@/api/adminAccountsApi", () => ({
  createBlockRequest: vi.fn(),
  getBlockPreflight: vi.fn(),
  getUserAdmins: vi.fn(),
  getRaisedBlockRequests: vi.fn(),
  reassignBlockRequest: vi.fn(),
  withdrawBlockRequest: vi.fn(),
}));
vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));

const PERSON = detailOf().person;

describe("BlockFromPurrf", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
    useAuth.mockReturnValue({ user: { userId: 9 } });
    getBlockPreflight.mockResolvedValue({
      data: { applicationCount: 0, interviewTimes: [] },
    });
    getUserAdmins.mockResolvedValue({
      data: [{ userId: 77, name: "Uma Admin" }],
    });
    getRaisedBlockRequests.mockResolvedValue({ data: [] });
  });

  const PENDING = {
    requestId: 5,
    reviewer: { userId: 77, name: "Uma Admin" },
  };
  const OWN = {
    id: 5,
    targetUserId: 3104,
    reviewerId: 77,
    reviewerName: "Uma Admin",
    reason: "private reason",
    raisedByName: "Dana Wu",
  };
  const renderPending = (props = {}) =>
    render(
      <BlockFromPurrf
        person={PERSON}
        canWrite
        pendingBlockRequest={PENDING}
        onRequested={vi.fn()}
        {...props}
      />,
    );

  it("tells the raiser who their request was sent to and offers reassign and withdraw", async () => {
    getRaisedBlockRequests.mockResolvedValue({
      data: [{ ...OWN, id: 9, targetUserId: 1 }, OWN],
    });
    renderPending();
    expect(
      await screen.findByText(/Block requested — sent to Uma Admin/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reassign" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Withdraw" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/waiting on/)).not.toBeInTheDocument();
  });

  it("withdraws the raiser's request and reloads the page", async () => {
    getRaisedBlockRequests.mockResolvedValue({ data: [OWN] });
    withdrawBlockRequest.mockResolvedValue({ data: {} });
    const onRequested = vi.fn();
    renderPending({ onRequested });
    await userEvent.click(
      await screen.findByRole("button", { name: "Withdraw" }),
    );
    await waitFor(() => expect(withdrawBlockRequest).toHaveBeenCalledWith(5));
    await waitFor(() => expect(onRequested).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith("Block request withdrawn.");
    expect(
      screen.queryByRole("button", { name: "Withdraw" }),
    ).not.toBeInTheDocument();
  });

  it("drops a withdrawn request at once, before the page reloads", async () => {
    getRaisedBlockRequests.mockResolvedValue({ data: [OWN] });
    withdrawBlockRequest.mockResolvedValue({ data: {} });
    renderPending({ onRequested: vi.fn() });
    await userEvent.click(
      await screen.findByRole("button", { name: "Withdraw" }),
    );
    expect(
      await screen.findByRole("button", { name: "Block from Purrf" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/waiting on/)).not.toBeInTheDocument();
    expect(screen.queryByText(/sent to/)).not.toBeInTheDocument();
  });

  it("offers reassign and withdraw right after raising, once the page shows the request", async () => {
    createBlockRequest.mockResolvedValue({ data: OWN });
    const props = { person: PERSON, canWrite: true, onRequested: vi.fn() };
    const { rerender } = render(
      <BlockFromPurrf {...props} pendingBlockRequest={null} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Block from Purrf" }),
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Reviewer"),
      "77",
    );
    await userEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(props.onRequested).toHaveBeenCalled());

    rerender(<BlockFromPurrf {...props} pendingBlockRequest={PENDING} />);
    expect(
      await screen.findByText(/Block requested — sent to Uma Admin/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reassign" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Withdraw" }),
    ).toBeInTheDocument();
  });

  it("reassigns to another admin, leaving out the current reviewer, the caller and the person", async () => {
    getRaisedBlockRequests.mockResolvedValue({ data: [OWN] });
    getUserAdmins.mockResolvedValue({
      data: [
        { userId: 77, name: "Uma Admin" },
        { userId: 9, name: "Caller Self" },
        { userId: 3104, name: "Alice Chen" },
        { userId: 88, name: "Omar Admin" },
      ],
    });
    reassignBlockRequest.mockResolvedValue({
      data: { ...OWN, reviewerId: 88, reviewerName: "Omar Admin" },
    });
    const onRequested = vi.fn();
    renderPending({ onRequested });
    await userEvent.click(
      await screen.findByRole("button", { name: "Reassign" }),
    );

    const select = await screen.findByLabelText("Reviewer");
    await within(select).findByRole("option", { name: "Omar Admin" });
    const names = within(select)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(names).not.toContain("Uma Admin");
    expect(names).not.toContain("Caller Self");
    expect(names).not.toContain("Alice Chen");

    await userEvent.selectOptions(select, "88");
    await userEvent.click(screen.getByRole("button", { name: "Reassign" }));
    await waitFor(() =>
      expect(reassignBlockRequest).toHaveBeenCalledWith(5, 88),
    );
    await waitFor(() => expect(onRequested).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith("Reassigned to Omar Admin.");
  });

  it("shows only who someone else's request waits on, with no controls and no reason", async () => {
    getRaisedBlockRequests.mockResolvedValue({
      data: [{ ...OWN, targetUserId: 1 }],
    });
    renderPending();
    expect(
      await screen.findByText("Block requested — waiting on Uma Admin"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reassign" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Withdraw" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/sent to/)).not.toBeInTheDocument();
    expect(screen.queryByText(/private reason/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Dana Wu/)).not.toBeInTheDocument();
  });

  it("says nothing about the request until the raised read settles", async () => {
    let resolve;
    getRaisedBlockRequests.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const { container } = renderPending();
    await waitFor(() => expect(getRaisedBlockRequests).toHaveBeenCalled());
    expect(screen.queryByText(/waiting on/)).not.toBeInTheDocument();
    expect(screen.queryByText(/sent to/)).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
    resolve({ data: [OWN] });
    expect(await screen.findByText(/sent to Uma Admin/)).toBeInTheDocument();
  });

  it("shows waiting on without reading the raised requests when the viewer cannot write", () => {
    renderPending({ canWrite: false });
    expect(
      screen.getByText("Block requested — waiting on Uma Admin"),
    ).toBeInTheDocument();
    expect(getRaisedBlockRequests).not.toHaveBeenCalled();
  });

  it("falls back to waiting on when the raised read fails", async () => {
    getRaisedBlockRequests.mockRejectedValue(new Error("boom"));
    renderPending();
    expect(
      await screen.findByText("Block requested — waiting on Uma Admin"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Withdraw" }),
    ).not.toBeInTheDocument();
  });

  it("says who a pending request waits on instead of offering another", async () => {
    render(
      <BlockFromPurrf
        person={PERSON}
        canWrite
        pendingBlockRequest={{
          requestId: 5,
          reviewer: { userId: 77, name: "Uma Admin" },
        }}
        onRequested={vi.fn()}
      />,
    );
    expect(
      await screen.findByText("Block requested — waiting on Uma Admin"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Block from Purrf" }),
    ).not.toBeInTheDocument();
  });

  it("offers nothing to someone already blocked", () => {
    const { container } = render(
      <BlockFromPurrf
        person={{ ...PERSON, isBlocked: true }}
        canWrite
        pendingBlockRequest={null}
        onRequested={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("offers nothing without write access", () => {
    const { container } = render(
      <BlockFromPurrf
        person={PERSON}
        canWrite={false}
        pendingBlockRequest={null}
        onRequested={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("raises the request from the mentorship page and tells the page", async () => {
    createBlockRequest.mockResolvedValue({
      data: { id: 5, reviewerName: "Uma Admin" },
    });
    const onRequested = vi.fn();
    render(
      <BlockFromPurrf
        person={PERSON}
        canWrite
        pendingBlockRequest={null}
        onRequested={onRequested}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Block from Purrf" }),
    );
    await waitFor(() => expect(getBlockPreflight).toHaveBeenCalledWith(3104));
    expect(getUserAdmins).toHaveBeenCalled();
    expect(
      screen.getByText(
        "This does not block anyone yet. It goes to the reviewer you name below, and nothing changes for this person until they approve it. You can reassign or withdraw it while it waits.",
      ),
    ).toBeInTheDocument();

    // ApprovalRequestDialog renders reviewers in a native <select>.
    await userEvent.selectOptions(
      await screen.findByLabelText("Reviewer"),
      "77",
    );
    await userEvent.click(screen.getByRole("button", { name: "Send request" }));

    await waitFor(() =>
      expect(createBlockRequest).toHaveBeenCalledWith(
        { userId: 3104, reason: "", reviewerId: 77 },
        "mentorship_participant",
      ),
    );
    expect(onRequested).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith(
      "Block requested — sent to Uma Admin.",
    );
  });
});
