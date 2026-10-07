import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AssignDialog from "@/pages/Inbox/AssignDialog";
import * as api from "@/api/inboxApi";

vi.mock("@/api/inboxApi", () => ({
  getInboxAssignOptions: vi.fn(),
  searchInboxPeople: vi.fn(),
}));

const thread = (over = {}) => ({
  threadId: 1,
  service: "mentorship",
  subject: "Hello",
  sender: "wang@example.com",
  person: { userId: 7, name: "Wang Xiao" },
  matchedBy: "alternative",
  assignment: null,
  ...over,
});

const setup = (t, props = {}) => {
  const onAssign = vi.fn();
  const onUnassign = vi.fn();
  const onCancel = vi.fn();
  render(
    <AssignDialog
      thread={t}
      onAssign={onAssign}
      onUnassign={onUnassign}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onAssign, onUnassign, onCancel };
};

beforeEach(() => vi.resetAllMocks());

describe("AssignDialog", () => {
  it("prefills the matched person and assigns a round", async () => {
    api.getInboxAssignOptions.mockResolvedValue({
      data: {
        rounds: [
          { roundId: 5, name: "Fall 2026", current: true, registered: false },
          { roundId: 4, name: "Spring 2026", current: false, registered: true },
        ],
      },
    });
    const { onAssign } = setup(thread());
    expect(screen.getByLabelText("Selected person")).toHaveTextContent(
      "Wang Xiao",
    );
    expect(screen.getByText("Matched by alternative email")).toBeInTheDocument();
    const select = await screen.findByLabelText("Round");
    expect(api.getInboxAssignOptions).toHaveBeenCalledWith(1, 7);
    expect(select).toHaveValue("5");
    expect(screen.getByText(/Fall 2026 \(current\)/)).toHaveTextContent(
      "Not registered",
    );
    fireEvent.change(select, { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 7, roundId: 4 });
  });

  it("searches for a person when the sender has no match", async () => {
    api.searchInboxPeople.mockResolvedValue({
      data: [{ userId: 9, name: "Lee Ann", email: "lee@example.com" }],
    });
    api.getInboxAssignOptions.mockResolvedValue({
      data: {
        rounds: [{ roundId: 1, name: "R1", current: true, registered: true }],
      },
    });
    const { onAssign } = setup(
      thread({ person: null, matchedBy: null, noMatchingUser: true }),
    );
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Search people"), {
      target: { value: "lee" },
    });
    fireEvent.click(await screen.findByRole("button", { name: /Lee Ann/ }));
    expect(api.searchInboxPeople).toHaveBeenCalledWith("lee");
    await screen.findByLabelText("Round");
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 9, roundId: 1 });
  });

  it("assigns a job for Recruiting and shows the fallback note", async () => {
    api.getInboxAssignOptions.mockResolvedValue({
      data: {
        jobs: [
          {
            jobId: 3,
            title: "Engineer",
            applicationId: 40,
            applicationStatus: "Interview",
            fallback: true,
          },
        ],
      },
    });
    const { onAssign } = setup(thread({ service: "recruiting" }));
    const select = await screen.findByLabelText("Job");
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    fireEvent.change(select, { target: { value: "3" } });
    expect(
      screen.getByText(/most recent application #40 \(Interview\)/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 7, jobId: 3 });
  });

  it("explains when a Recruiting person has no jobs", async () => {
    api.getInboxAssignOptions.mockResolvedValue({ data: { jobs: [] } });
    setup(thread({ service: "recruiting" }));
    expect(await screen.findByText(/can't be assigned/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
  });

  it("offers Remove assignment for an assigned thread", async () => {
    api.getInboxAssignOptions.mockResolvedValue({ data: { rounds: [] } });
    const { onUnassign } = setup(
      thread({
        assignment: { kind: "round", roundId: 4, roundName: "Spring 2026" },
      }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Remove assignment" }),
    );
    await waitFor(() => expect(onUnassign).toHaveBeenCalled());
  });
});
