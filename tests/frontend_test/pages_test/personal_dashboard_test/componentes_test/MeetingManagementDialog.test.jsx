import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import MeetingManagementDialog from "@/pages/PersonalDashboard/components/MeetingManagementDialog";
import { useMeetingManagement } from "@/pages/PersonalDashboard/hooks/useMeetingManagement";

vi.mock("@/pages/PersonalDashboard/hooks/useMeetingManagement", () => ({
  useMeetingManagement: vi.fn(),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

// Mock TimezoneSelector to simplify option interaction in JSDOM
vi.mock("@/components/common/TimezoneSelector", () => ({
  default: ({ value, onChange }) => (
    <select
      data-testid="timezone-selector"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value={localTimezone}>{localTimezone}</option>
      <option value="America/New_York">America/New_York</option>
      <option value="Asia/Shanghai">Asia/Shanghai</option>
    </select>
  ),
}));

// The log form is exercised in its own suite; here only its presence matters.
vi.mock("@/pages/PersonalDashboard/components/MeetingLogForm", () => ({
  default: ({ roundId, partnerId }) => (
    <div data-testid="meeting-log-form">
      <span data-testid="log-form-round">{String(roundId)}</span>
      <span data-testid="log-form-partner">{String(partnerId)}</span>
      <button>Log Meeting</button>
    </div>
  ),
}));

// Mock static datasets
const mockPartners = new Map([
  [
    1,
    {
      id: 1,
      name: "John Doe",
      preferredName: "Johnny",
      email: "john@test.com",
      isActive: true,
    },
  ],
  [
    2,
    {
      id: 2,
      name: "Alice Smith",
      preferredName: "",
      email: "alice@test.com",
      isActive: true,
    },
  ],
]);

const mockBookMeeting = vi.fn();
const mockRefresh = vi.fn();
const mockOnBooked = vi.fn();

// Start Time is a real (unmocked) react-select; open its menu and pick an option.
async function selectStartTime(timeLabel) {
  fireEvent.keyDown(screen.getByLabelText("Start Time"), { key: "ArrowDown" });
  fireEvent.click(await screen.findByText(timeLabel));
}

describe("MeetingManagementDialog Component", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    // Default hook state setup
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      refresh: mockRefresh,
      isLoading: false,
    });

    document.body.style.pointerEvents = "auto";
    document.body.removeAttribute("data-scroll-locked");
  });

  it("should disable the trigger and surface the reason when no tab is usable", () => {
    const { rerender } = render(
      <MeetingManagementDialog
        roundId={2}
        scheduleUnavailableReason="No active mentorship round"
      />,
    );

    const triggerButton = screen.getByRole("button", {
      name: /manage meetings/i,
    });
    expect(triggerButton).toBeDisabled();

    const wrapperDiv = triggerButton.closest("div");
    expect(wrapperDiv).toHaveAttribute("title", "No active mentorship round");

    // Re-render with the round schedulable to verify enablement
    rerender(<MeetingManagementDialog roundId={2} />);
    expect(
      screen.getByRole("button", { name: /manage meetings/i }),
    ).not.toBeDisabled();
  });

  it("should not offer a partner whose pairing has ended", async () => {
    // The partner list doubles as the name lookup for meetings already held,
    // so it carries pairings that have ended. Booking against one is refused
    // by the backend, so it is not offered here.
    useMeetingManagement.mockReturnValue({
      partners: new Map([
        ...mockPartners,
        [
          3,
          {
            id: 3,
            preferredName: "Bob Ended",
            email: "bob@test.com",
            isActive: false,
          },
        ],
      ]),
      bookMeeting: mockBookMeeting,
      refresh: mockRefresh,
      isLoading: false,
    });

    render(<MeetingManagementDialog roundId="1" />);
    fireEvent.click(screen.getByRole("button", { name: /Manage Meetings/ }));

    const select = await screen.findByLabelText("Select Partner");
    expect(
      within(select).getByRole("option", { name: /Johnny/ }),
    ).toBeInTheDocument();
    expect(
      within(select).queryByRole("option", { name: /Bob Ended/ }),
    ).not.toBeInTheDocument();
  });

  it("should open the dialog onto the scheduling form", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    const triggerButton = screen.getByRole("button", {
      name: /manage meetings/i,
    });
    await userEvent.click(triggerButton);

    // Verify dialog header text and default scheduling fields are active
    expect(screen.getByText("Meeting Management")).toBeInTheDocument();

    const partnerSelect = document.querySelector('select[name="partnerId"]');
    expect(partnerSelect).toBeInTheDocument();

    // Cancelling lives on the participation card now, so scheduling is the
    // only thing this viewer's dialog holds.
    expect(screen.getAllByRole("tab")).toHaveLength(1);
    expect(
      screen.queryByRole("tab", { name: /uncompleted/i }),
    ).not.toBeInTheDocument();
  });

  it("should handle submission validation if required fields are missing", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    // Open Dialog
    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    const scheduleTab = screen.getByRole("tab", { name: /schedule meeting/i });
    await userEvent.click(scheduleTab);

    const form = screen.getByRole("dialog").querySelector("form");
    if (!form) throw new Error("Form still not found in DOM");
    fireEvent.submit(form);

    expect(mockBookMeeting).not.toHaveBeenCalled();
  });

  it("should reset form data with a 200ms delay after the dialog is closed", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    let partnerSelect = screen.getByRole("combobox", {
      name: /select partner/i,
    });
    await userEvent.selectOptions(partnerSelect, "1");

    fireEvent.keyDown(document.activeElement || document.body, {
      key: "Escape",
      code: "Escape",
    });
    await new Promise((resolve) => setTimeout(resolve, 250));

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    const refreshedPartnerSelect = screen.getByRole("combobox", {
      name: /select partner/i,
    });
    expect(refreshedPartnerSelect.value).toBe("");
  });

  it("should submit a wall-clock payload (no client-side UTC conversion)", async () => {
    // Pin today to 2026-07-15 so the calendar opens on July 2026.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-07-15T12:00:00-04:00"));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockBookMeeting.mockResolvedValue({
      created: [{ meetingId: "g-1" }],
      failed: [],
    });

    render(
      <MeetingManagementDialog
        roundId={5}
        onBooked={vi.fn()}
        userTimezone="America/New_York"
      />,
    );
    await user.click(screen.getByRole("button", { name: /manage meetings/i }));

    await user.selectOptions(screen.getByLabelText("Select Partner"), "1");
    fireEvent.change(screen.getByTestId("timezone-selector"), {
      target: { value: "America/New_York" },
    });

    // Open the date popover and pick July 30, 2026.
    await user.click(screen.getByRole("button", { name: /pick a date/i }));
    // react-day-picker renders each day as a button; its accessible name
    // contains the day-of-month. Match the "30" cell within the open dialog.
    const dayButtons = screen.getAllByRole("button", { name: /30/ });
    await user.click(dayButtons[dayButtons.length - 1]);

    await selectStartTime("09:00");

    fireEvent.submit(document.querySelector("form"));

    await waitFor(() => {
      expect(mockBookMeeting).toHaveBeenCalledWith({
        round_id: 5,
        partner_id: 1,
        timezone: "America/New_York",
        start_date: "2026-07-30",
        start_time: "09:00",
        duration_minutes: 30,
        interval_weeks: 1,
        count: 1,
      });
    });

    vi.useRealTimers();
  });

  it("should send interval_weeks and count when a recurrence is chosen", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-07-15T12:00:00-04:00"));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockBookMeeting.mockResolvedValue({
      created: [{ meetingId: "g-1" }],
      failed: [],
    });

    render(
      <MeetingManagementDialog
        roundId={5}
        onBooked={vi.fn()}
        userTimezone="America/New_York"
      />,
    );
    await user.click(screen.getByRole("button", { name: /manage meetings/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Select Partner"), "1");
    fireEvent.change(screen.getByTestId("timezone-selector"), {
      target: { value: "America/New_York" },
    });
    await user.click(screen.getByRole("button", { name: /pick a date/i }));
    const dayButtons = screen.getAllByRole("button", { name: /30/ });
    await user.click(dayButtons[dayButtons.length - 1]);

    const repeatSelect = await screen.findByLabelText(/repeat every/i);
    const countSelect = await screen.findByLabelText(/number of sessions/i);
    fireEvent.change(repeatSelect, { target: { value: "2" } });
    fireEvent.change(countSelect, { target: { value: "4" } });

    await selectStartTime("09:00");

    fireEvent.submit(document.querySelector("form"));

    await waitFor(() => {
      expect(mockBookMeeting).toHaveBeenCalledWith({
        round_id: 5,
        partner_id: 1,
        timezone: "America/New_York",
        start_date: "2026-07-30",
        start_time: "09:00",
        duration_minutes: 30,
        interval_weeks: 2,
        count: 4,
      });
    });
    vi.useRealTimers();
  });

  it("shows a partial-failure toast when some sessions fail", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-07-15T12:00:00-04:00"));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    mockBookMeeting.mockResolvedValue({
      created: [{ meetingId: "g-1" }, { meetingId: "g-2" }],
      failed: [
        { index: 2, startDatetime: "2026-08-13T14:00:00Z", reason: "boom" },
      ],
    });

    render(
      <MeetingManagementDialog
        roundId={2}
        onBooked={mockOnBooked}
        userTimezone="America/New_York"
      />,
    );

    await user.click(screen.getByRole("button", { name: /manage meetings/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Select Partner"), "1");

    fireEvent.change(screen.getByTestId("timezone-selector"), {
      target: { value: "America/New_York" },
    });

    await user.click(screen.getByRole("button", { name: /pick a date/i }));
    const dayButtons = screen.getAllByRole("button", { name: /30/ });
    await user.click(dayButtons[dayButtons.length - 1]);

    const repeatSelect = await screen.findByLabelText(/repeat every/i);
    const countSelect = await screen.findByLabelText(/number of sessions/i);
    fireEvent.change(repeatSelect, { target: { value: "1" } });
    fireEvent.change(countSelect, { target: { value: "3" } });

    await selectStartTime("09:00");

    fireEvent.submit(document.querySelector("form"));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Created 2 of 3 sessions (1 failed)",
      );
    });

    vi.useRealTimers();
  });
});

describe("MeetingManagementDialog entry point", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      refresh: mockRefresh,
      isLoading: false,
    });
    document.body.style.pointerEvents = "auto";
    document.body.removeAttribute("data-scroll-locked");
  });

  it("should render nothing when neither scheduling nor logging is offered", () => {
    const { container } = render(
      <MeetingManagementDialog
        roundId={2}
        canSchedule={false}
        canLogPast={false}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("should not offer the log tab when logging is not available to this viewer", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    expect(
      screen.queryByRole("tab", { name: /log past meeting/i }),
    ).not.toBeInTheDocument();
  });

  it("should open straight to the log tab when logging is the only thing offered", async () => {
    render(
      <MeetingManagementDialog
        roundId={7}
        canSchedule={false}
        canLogPast={true}
        logPartnerId={9}
      />,
    );

    const trigger = screen.getByRole("button", { name: /manage meetings/i });
    expect(trigger).not.toBeDisabled();
    await userEvent.click(trigger);

    expect(
      screen.queryByRole("tab", { name: /schedule meeting/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("meeting-log-form")).toBeInTheDocument();
    expect(screen.getByTestId("log-form-round")).toHaveTextContent("7");
    expect(screen.getByTestId("log-form-partner")).toHaveTextContent("9");
  });

  it("should open on the log tab when the round cannot be scheduled in but can still be logged against", async () => {
    // A round that has ended still accepts meetings held before it closed, so
    // the entry point stays reachable rather than following the schedule tab
    // into being disabled.
    render(
      <MeetingManagementDialog
        roundId={2}
        scheduleUnavailableReason="No active mentorship round"
        canLogPast={true}
        logPartnerId={9}
      />,
    );

    const trigger = screen.getByRole("button", { name: /manage meetings/i });
    expect(trigger).not.toBeDisabled();
    await userEvent.click(trigger);

    expect(screen.getByTestId("meeting-log-form")).toBeInTheDocument();
  });

  it("should show the reason in place of the schedule form when the round is not active", async () => {
    render(
      <MeetingManagementDialog
        roundId={2}
        scheduleUnavailableReason="No active mentorship round"
        canLogPast={true}
        logPartnerId={9}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(
      screen.getByRole("tab", { name: /schedule meeting/i }),
    );

    expect(screen.getByText("No active mentorship round")).toBeInTheDocument();
    expect(
      document.querySelector('select[name="partnerId"]'),
    ).not.toBeInTheDocument();
  });

  it("should show the reason in place of the log form when logging is unavailable", async () => {
    render(
      <MeetingManagementDialog
        roundId={2}
        canLogPast={true}
        logUnavailableReason="Logging meetings for this round has closed."
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(
      screen.getByRole("tab", { name: /log past meeting/i }),
    );

    expect(
      screen.getByText("Logging meetings for this round has closed."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("meeting-log-form")).not.toBeInTheDocument();
  });
});
