import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MeetingSubmissionModal from "@/pages/PersonalDashboard/components/MeetingSubmissionModal";
import { postMyMentorshipMeetingLog } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  postMyMentorshipMeetingLog: vi.fn(),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({ value, onValueChange, children }) => (
    <select value={value} onChange={(e) => onValueChange(e.target.value)}>
      {children}
    </select>
  ),
  SelectTrigger: () => null,
  SelectValue: () => null,
  SelectContent: ({ children }) => children,
  SelectItem: ({ value, children }) => (
    <option value={value}>{children}</option>
  ),
}));

vi.mock("react-timezone-select", () => ({
  default: ({ value, onChange }) => (
    <select
      data-testid="timezone-select"
      value={typeof value === "string" ? value : value?.value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="Asia/Shanghai">Asia/Shanghai</option>
      <option value="America/New_York">America/New_York</option>
    </select>
  ),
}));

describe("MeetingSubmissionModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should not render when closed", () => {
    render(
      <MeetingSubmissionModal
        open={false}
        onOpenChange={vi.fn()}
        roundId="1"
        onSuccess={vi.fn()}
      />,
    );
    expect(screen.queryByText("Submit Meeting Info")).not.toBeInTheDocument();
  });

  it("should render all form fields when open", () => {
    render(
      <MeetingSubmissionModal
        open={true}
        onOpenChange={vi.fn()}
        roundId="1"
        onSuccess={vi.fn()}
      />,
    );
    expect(screen.getByText("Submit Meeting Info")).toBeInTheDocument();
    expect(screen.getByText("Timezone")).toBeInTheDocument();
    expect(screen.getByText("Date")).toBeInTheDocument();
    expect(screen.getByText("Start Time")).toBeInTheDocument();
    expect(screen.getByText("End Time")).toBeInTheDocument();
  });

  it("should call postMyMentorshipMeetingLog with the correct payload on submit", async () => {
    postMyMentorshipMeetingLog.mockResolvedValue({});
    const onSuccess = vi.fn();

    render(
      <MeetingSubmissionModal
        open={true}
        onOpenChange={vi.fn()}
        roundId="42"
        userTimezone="Asia/Shanghai"
        onSuccess={onSuccess}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(postMyMentorshipMeetingLog).toHaveBeenCalledWith(
        expect.objectContaining({
          roundId: 42,
          startDatetime: expect.stringContaining("T"),
          endDatetime: expect.stringContaining("T"),
          isCompleted: true,
        }),
      );
    });

    expect(onSuccess).toHaveBeenCalled();
  });

  it("should show an error when start and end time are the same", async () => {
    render(
      <MeetingSubmissionModal
        open={true}
        onOpenChange={vi.fn()}
        roundId="1"
        onSuccess={vi.fn()}
      />,
    );

    // combobox[0] = timezone, combobox[1] = Start Time, combobox[2] = End Time
    const comboboxes = screen.getAllByRole("combobox");
    fireEvent.change(comboboxes[2], { target: { value: "10:00" } });

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(
        screen.getByText("Start time and end time cannot be the same."),
      ).toBeInTheDocument();
    });
    expect(postMyMentorshipMeetingLog).not.toHaveBeenCalled();
  });

  it("should show a slot error when the backend returns a time conflict", async () => {
    const conflictError = {
      response: { data: { message: "This time slot already exists." } },
    };
    postMyMentorshipMeetingLog.mockRejectedValue(conflictError);

    render(
      <MeetingSubmissionModal
        open={true}
        onOpenChange={vi.fn()}
        roundId="1"
        onSuccess={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(
        screen.getByText("This time slot already exists."),
      ).toBeInTheDocument();
    });
  });

  it("should disable the Submit button while submitting", async () => {
    // Keep the promise pending to hold the submitting state
    postMyMentorshipMeetingLog.mockImplementation(() => new Promise(() => {}));

    render(
      <MeetingSubmissionModal
        open={true}
        onOpenChange={vi.fn()}
        roundId="1"
        onSuccess={vi.fn()}
      />,
    );

    const submitBtn = screen.getByRole("button", { name: "Submit" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(submitBtn).toBeDisabled();
    });
  });
});
