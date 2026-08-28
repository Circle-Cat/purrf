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

const mockUpcomingMeetings = [
  {
    meetingId: "m-1",
    partnerId: 1,
    partnerName: "Johnny",
    partnerRole: "mentee",
    partnerEmail: "john@test.com",
    startDatetime: "2026-07-15T09:00:00.000Z",
    endDatetime: "2026-07-15T09:30:00.000Z",
  },
  {
    meetingId: "m-2",
    partnerId: 2,
    partnerName: "Alice Smith",
    partnerRole: "mentor",
    partnerEmail: "alice@test.com",
    startDatetime: "2026-07-02T11:00:00.000Z",
    endDatetime: "2026-07-02T11:30:00.000Z",
  },
];

const mockBookMeeting = vi.fn();
const mockCancelMeetings = vi.fn();
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
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: [],
      isLoading: false,
    });

    document.body.style.pointerEvents = "auto";
    document.body.removeAttribute("data-scroll-locked");
  });

  it("should disable the button and show correct tooltip when roundId is invalid", () => {
    const { rerender } = render(<MeetingManagementDialog roundId={null} />);

    const triggerButton = screen.getByRole("button", {
      name: /manage meetings/i,
    });
    expect(triggerButton).toBeDisabled();

    const wrapperDiv = triggerButton.closest("div");
    expect(wrapperDiv).toHaveAttribute("title", "No active mentorship round");

    // Re-render with valid roundId to verify enablement
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
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: [],
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

  it("should open the dialog and switch tabs correctly when interactions occur", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    const triggerButton = screen.getByRole("button", {
      name: /manage meetings/i,
    });
    await userEvent.click(triggerButton);

    // Verify dialog header text and default scheduling fields are active
    expect(screen.getByText("Meeting Management")).toBeInTheDocument();

    const partnerSelect = document.querySelector('select[name="partnerId"]');
    expect(partnerSelect).toBeInTheDocument();

    // Switch to the 'Upcoming' tab
    const upcomingTab = screen.getByRole("tab", { name: /upcoming/i });
    await userEvent.click(upcomingTab);

    // Verify the empty state placeholder text is visible
    expect(screen.getByText("No upcoming meetings found")).toBeInTheDocument();
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

  it("should successfully cancel a single selected meeting", async () => {
    const activeMeetings = [
      {
        meetingId: "m-1",
        partnerId: 1,
        partnerName: "Test Partner",
        startDatetime: "2026-07-02T10:00:00Z",
        endDatetime: "2026-07-02T11:00:00Z",
        timezoneStr: "Asia/Shanghai",
      },
    ];

    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: activeMeetings,
      upcomingLength: 1,
      isLoading: false,
    });

    render(<MeetingManagementDialog roundId={2} onBooked={mockOnBooked} />);

    // Open the dialog trigger
    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    // Switch to the Upcoming Tab
    const upcomingTab = screen.getByRole("tab", { name: /upcoming/i });
    await userEvent.click(upcomingTab);

    // Wait asynchronously to retrieve the specific checkbox
    const checkbox = await waitFor(() => {
      const el = document.getElementById("check-m-1");
      if (!el) throw new Error("Waiting for checkbox to render...");
      return el;
    });

    // Select the item
    await userEvent.click(checkbox);

    // Target the delete button once enabled
    const deleteButton = await screen.findByRole("button", {
      name: /delete \(1\)/i,
    });

    // Execute the deletion action
    await userEvent.click(deleteButton);

    // Verify standard payload filtering and subsequent view refreshes
    await waitFor(() => {
      expect(mockCancelMeetings).toHaveBeenCalledWith([
        expect.objectContaining({
          meetingId: "m-1",
          partnerName: "Test Partner",
        }),
      ]);
      expect(mockOnBooked).toHaveBeenCalled();
    });
  });

  it("should successfully batch cancel all meetings when 'Select All' is checked", async () => {
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: mockUpcomingMeetings,
      upcomingLength: mockUpcomingMeetings.length,
      isLoading: false,
    });

    render(<MeetingManagementDialog roundId={2} onBooked={mockOnBooked} />);

    // Open dialog and toggle views
    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(screen.getByRole("tab", { name: /upcoming/i }));

    // Locate the "Select All" target element
    const selectAllCheckbox = await waitFor(() => {
      const el = document.getElementById("select-all-upcoming");
      if (!el)
        throw new Error(
          "Timeout: select-all-upcoming master checkbox element not found",
        );
      return el;
    });

    // Trigger Radix state change via click interaction
    await userEvent.click(selectAllCheckbox);

    // Wait for batch delete confirmation control to become interactive
    const deleteButton = await screen.findByRole("button", {
      name: new RegExp(`delete \\(${mockUpcomingMeetings.length}\\)`, "i"),
    });

    // Perform final deletion click
    await userEvent.click(deleteButton);

    // Validation: Ensure full collection transmission and state synchandlers run successfully
    await waitFor(() => {
      expect(mockCancelMeetings).toHaveBeenCalledWith(mockUpcomingMeetings);
      expect(mockOnBooked).toHaveBeenCalled();
    });
  });

  it("should uncheck all items and disable delete button when clicking 'Select All' twice", async () => {
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: mockUpcomingMeetings,
      upcomingLength: mockUpcomingMeetings.length,
      isLoading: false,
    });

    render(<MeetingManagementDialog roundId={2} />);

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(screen.getByRole("tab", { name: /upcoming/i }));

    const selectAllCheckbox = await waitFor(() =>
      document.getElementById("select-all-upcoming"),
    );

    // First interaction: Select All
    await userEvent.click(selectAllCheckbox);
    const deleteButton = await screen.findByRole("button", {
      name: /delete \(2\)/i,
    });
    expect(deleteButton).not.toBeDisabled();

    // Second interaction: Deselect All
    await userEvent.click(selectAllCheckbox);

    // Assertions: Ensure delete metric tracking drops to 0 and becomes disabled
    await waitFor(() => {
      const updatedDeleteButton = screen.getByRole("button", {
        name: /delete \(0\)/i,
      });
      expect(updatedDeleteButton).toBeDisabled();
    });
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

  it("should clear selectedIds when switching tabs or closing the dialog", async () => {
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: mockUpcomingMeetings,
      upcomingLength: mockUpcomingMeetings.length,
      isLoading: false,
    });

    render(<MeetingManagementDialog roundId={2} />);

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(screen.getByRole("tab", { name: /upcoming/i }));

    const checkbox = await waitFor(() => document.getElementById("check-m-1"));
    await userEvent.click(checkbox);
    expect(
      screen.getByRole("button", { name: /delete \(1\)/i }),
    ).not.toBeDisabled();

    // Navigate to alternative workflow views
    await userEvent.click(
      screen.getByRole("tab", { name: /schedule meeting/i }),
    );
    // Return back to tracking panel
    await userEvent.click(screen.getByRole("tab", { name: /upcoming/i }));

    // Assertions: Side-effects should clear prior cached selections to prevent dangling reference deletes
    expect(
      screen.getByRole("button", { name: /delete \(0\)/i }),
    ).toBeDisabled();
  });

  it("should reset selection when upcomingMeetings length changes from outside", async () => {
    // Initialize list with multiple items
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      upcomingMeetings: mockUpcomingMeetings,
      upcomingLength: mockUpcomingMeetings.length,
      isLoading: false,
    });

    const { rerender } = render(<MeetingManagementDialog roundId={2} />);

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(screen.getByRole("tab", { name: /upcoming/i }));

    const checkbox = await waitFor(() => document.getElementById("check-m-1"));
    await userEvent.click(checkbox);
    expect(
      screen.getByRole("button", { name: /delete \(1\)/i }),
    ).not.toBeDisabled();

    // Simulate upstream sync modifications
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      upcomingMeetings: [mockUpcomingMeetings[0]],
      upcomingLength: 1,
      isLoading: false,
    });

    rerender(<MeetingManagementDialog roundId={2} />);

    // Assertions: Cache resets correctly upon collection updates via hook side effects
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /delete \(0\)/i }),
      ).toBeDisabled();
    });
  });

  it("should show the full IANA zone name (not a city fragment) on upcoming meeting cards", async () => {
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: mockUpcomingMeetings,
      upcomingLength: mockUpcomingMeetings.length,
      isLoading: false,
    });

    render(
      <MeetingManagementDialog roundId={2} userTimezone="Asia/Shanghai" />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(screen.getByRole("tab", { name: /upcoming/i }));

    expect(screen.getAllByText("Asia/Shanghai").length).toBeGreaterThan(0);
    expect(screen.queryByText("Shanghai")).not.toBeInTheDocument();
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

  it("should render a Join link only for an upcoming meeting that has a meet link", async () => {
    // m-1 was created through Google and carries a link; m-2 stands in for a
    // manually logged meeting, which never has one.
    const meetings = [
      {
        ...mockUpcomingMeetings[0],
        meetLink: "https://meet.google.com/abc-defg-hij",
      },
      mockUpcomingMeetings[1],
    ];
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      cancelMeetings: mockCancelMeetings,
      refresh: mockRefresh,
      upcomingMeetings: meetings,
      upcomingLength: meetings.length,
      isLoading: false,
    });

    render(
      <MeetingManagementDialog roundId={2} userTimezone="Asia/Shanghai" />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );
    await userEvent.click(screen.getByRole("tab", { name: /upcoming/i }));

    const joinLinks = screen.getAllByRole("link", { name: /join/i });
    expect(joinLinks).toHaveLength(1);
    expect(joinLinks[0]).toHaveAttribute(
      "href",
      "https://meet.google.com/abc-defg-hij",
    );
    expect(joinLinks[0]).toHaveAttribute("target", "_blank");
    expect(joinLinks[0]).toHaveAttribute(
      "rel",
      expect.stringContaining("noopener"),
    );
  });
});
