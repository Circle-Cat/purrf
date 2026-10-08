import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import BlockFromPurrf from "@/pages/MentorshipManagement/components/BlockFromPurrf";
import {
  createBlockRequest,
  getBlockPreflight,
  getUserAdmins,
} from "@/api/adminAccountsApi";
import { useAuth } from "@/context/auth";
import { detailOf } from "../participantDetail.helper";

vi.mock("@/api/adminAccountsApi", () => ({
  createBlockRequest: vi.fn(),
  getBlockPreflight: vi.fn(),
  getUserAdmins: vi.fn(),
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
  });

  it("says who a pending request waits on instead of offering another", () => {
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
      screen.getByText("Block requested — waiting on Uma Admin"),
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
