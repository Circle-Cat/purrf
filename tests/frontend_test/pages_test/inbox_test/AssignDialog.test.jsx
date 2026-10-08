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

  it("defaults to the live application and assigns it for Recruiting", async () => {
    api.getInboxAssignOptions.mockResolvedValue(
      recruitingOptions([engineer, designer]),
    );
    const { onAssign } = setup(thread({ service: "recruiting" }));
    const job = await screen.findByLabelText("Job");
    expect(
      screen.getByText("Only employment jobs this person applied to."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Application")).toBeNull();
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    fireEvent.change(job, { target: { value: "3" } });
    const app = screen.getByLabelText("Application");
    expect(app).toHaveValue("41");
    expect(
      screen.getByRole("option", { name: "#41 · Tech · Applied Sep 3, 2026" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: "#52 · Rejected · Applied Sep 20, 2026",
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 7, applicationId: 41 });
  });

  it("defaults to the newest application when all are rejected", async () => {
    api.getInboxAssignOptions.mockResolvedValue(recruitingOptions([designer]));
    setup(thread({ service: "recruiting" }));
    fireEvent.change(await screen.findByLabelText("Job"), {
      target: { value: "8" },
    });
    expect(screen.getByLabelText("Application")).toHaveValue("77");
  });

  it("resets the application when the job changes", async () => {
    api.getInboxAssignOptions.mockResolvedValue(
      recruitingOptions([engineer, designer]),
    );
    const { onAssign } = setup(thread({ service: "recruiting" }));
    const job = await screen.findByLabelText("Job");
    fireEvent.change(job, { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Application"), {
      target: { value: "30" },
    });
    expect(screen.getByLabelText("Application")).toHaveValue("30");
    fireEvent.change(job, { target: { value: "8" } });
    expect(screen.getByLabelText("Application")).toHaveValue("77");
    fireEvent.change(job, { target: { value: "" } });
    expect(screen.queryByLabelText("Application")).toBeNull();
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    fireEvent.change(job, { target: { value: "3" } });
    expect(screen.getByLabelText("Application")).toHaveValue("41");
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 7, applicationId: 41 });
  });

  it("shows the select even for a single application", async () => {
    api.getInboxAssignOptions.mockResolvedValue(
      recruitingOptions([
        {
          jobId: 5,
          title: "Analyst",
          applications: [
            {
              applicationId: 90,
              stage: "recruiter_screening",
              appliedAt: "2026-10-01T12:00:00Z",
            },
          ],
        },
      ]),
    );
    const { onAssign } = setup(thread({ service: "recruiting" }));
    fireEvent.change(await screen.findByLabelText("Job"), {
      target: { value: "5" },
    });
    expect(screen.getByLabelText("Application")).toHaveValue("90");
    expect(
      screen.getByRole("option", {
        name: "#90 · Recruiter screening · Applied Oct 1, 2026",
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(onAssign).toHaveBeenCalledWith({ userId: 7, applicationId: 90 });
  });

  it("resets job and application when the person changes", async () => {
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
    fireEvent.change(await screen.findByLabelText("Job"), {
      target: { value: "3" },
    });
    expect(screen.getByLabelText("Application")).toHaveValue("41");
    fireEvent.click(screen.getByRole("button", { name: "Change" }));
    fireEvent.change(screen.getByLabelText("Search people"), {
      target: { value: "lee" },
    });
    fireEvent.click(await screen.findByRole("button", { name: /Lee Ann/ }));
    expect(await screen.findByLabelText("Job")).toHaveValue("");
    expect(api.getInboxAssignOptions).toHaveBeenLastCalledWith(1, 9);
    expect(screen.queryByLabelText("Application")).toBeNull();
    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Job"), { target: { value: "8" } });
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
