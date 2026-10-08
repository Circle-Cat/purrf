import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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
  ...over,
});

const setup = (t, props = {}) => {
  const onAssign = vi.fn();
  const onCancel = vi.fn();
  render(
    <AssignDialog
      thread={t}
      onAssign={onAssign}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onAssign, onCancel };
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
    expect(
      screen.getByText("Matched by alternative email"),
    ).toBeInTheDocument();
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

  const recruitingOptions = (jobs) => ({
    success: true,
    message: "",
    data: { jobs },
  });

  const engineer = {
    jobId: 3,
    title: "Engineer",
    kind: "employment",
    applications: [
      {
        applicationId: 52,
        stage: "rejected",
        appliedAt: "2026-09-20T12:00:00Z",
      },
      { applicationId: 41, stage: "tech", appliedAt: "2026-09-03T12:00:00Z" },
      {
        applicationId: 30,
        stage: "rejected",
        appliedAt: "2026-06-01T12:00:00Z",
      },
    ],
  };
  const designer = {
    jobId: 8,
    title: "Designer",
    kind: "employment",
    applications: [
      {
        applicationId: 77,
        stage: "rejected",
        appliedAt: "2026-08-15T12:00:00Z",
      },
      {
        applicationId: 61,
        stage: "rejected",
        appliedAt: "2026-05-02T12:00:00Z",
      },
    ],
  };

  it("picks any application, grouped by job, for Recruiting", async () => {
    api.getInboxAssignOptions.mockResolvedValue(
      recruitingOptions([engineer, designer]),
    );
    const { onAssign } = setup(thread({ service: "recruiting" }));
    const app = await screen.findByLabelText("Application");
    expect(screen.queryByLabelText("Job")).toBeNull();
    expect(app).toHaveValue("");
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    expect([...app.querySelectorAll("optgroup")].map((g) => g.label)).toEqual([
      "Engineer",
      "Designer",
    ]);
    expect(
      screen.getByRole("option", { name: "#41 · Tech · Applied Sep 3, 2026" }),
    ).toBeInTheDocument();
    fireEvent.change(app, { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 7, applicationId: 30 });
  });

  it("names an activity job's hired stage Admitted", async () => {
    const mentee = {
      jobId: 12,
      title: "Mentee 2026",
      kind: "activity",
      applications: [
        {
          applicationId: 90,
          stage: "hired",
          appliedAt: "2026-04-10T12:00:00Z",
        },
      ],
    };
    api.getInboxAssignOptions.mockResolvedValue(
      recruitingOptions([mentee, engineer]),
    );
    const { onAssign } = setup(thread({ service: "recruiting" }));
    fireEvent.change(await screen.findByLabelText("Application"), {
      target: { value: "90" },
    });
    expect(
      screen.getByRole("option", {
        name: "#90 · Admitted · Applied Apr 10, 2026",
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 7, applicationId: 90 });
  });

  it("clears the application when the person changes", async () => {
    api.searchInboxPeople.mockResolvedValue({
      success: true,
      message: "",
      data: [{ userId: 9, name: "Lee Ann", email: "lee@example.com" }],
    });
    api.getInboxAssignOptions.mockImplementation((_id, userId) =>
      Promise.resolve(
        recruitingOptions(userId === 7 ? [engineer] : [designer]),
      ),
    );
    const { onAssign } = setup(thread({ service: "recruiting" }));
    fireEvent.change(await screen.findByLabelText("Application"), {
      target: { value: "41" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change" }));
    fireEvent.change(screen.getByLabelText("Search people"), {
      target: { value: "lee" },
    });
    fireEvent.click(await screen.findByRole("button", { name: /Lee Ann/ }));
    expect(await screen.findByLabelText("Application")).toHaveValue("");
    expect(api.getInboxAssignOptions).toHaveBeenLastCalledWith(1, 9);
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Application"), {
      target: { value: "77" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 9, applicationId: 77 });
  });

  it("explains when a Recruiting person has no jobs", async () => {
    api.getInboxAssignOptions.mockResolvedValue({
      success: true,
      message: "",
      data: { jobs: [] },
    });
    setup(thread({ service: "recruiting" }));
    expect(await screen.findByText(/can't be assigned/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
  });

  it("has no Remove assignment action", async () => {
    api.getInboxAssignOptions.mockResolvedValue({ data: { rounds: [] } });
    setup(thread());
    expect(screen.getByRole("heading", { name: "Assign thread" })).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Remove assignment" }),
    ).toBeNull();
  });
});
