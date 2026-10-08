// tests/frontend_test/pages_test/mentorship_management_test/components_test/MeetingLogTable.test.jsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { toast } from "sonner";
import MeetingLogTable, {
  MeetingLogEditButtons,
} from "@/pages/MentorshipManagement/components/MeetingLogTable";
import { useMeetingLogEditor } from "@/pages/MentorshipManagement/hooks/useMeetingLogEditor";

vi.spyOn(toast, "error").mockImplementation(() => {});

const meeting = (overrides = {}) => ({
  meetingId: "gm-80-1",
  startDatetime: "2024-03-01T23:30:00Z",
  endDatetime: "2024-03-02T00:30:00Z",
  isCompleted: true,
  note: [],
  createDatetime: "2024-03-01T15:30:00Z",
  ...overrides,
});

// Harness: the table plus its buttons, wired to one editor, the way the
// detail page uses them.
const Harness = ({ meetings, onSave = vi.fn().mockResolvedValue() }) => {
  const editor = useMeetingLogEditor({ meetings, onSave });
  return (
    <>
      <MeetingLogTable
        meetings={meetings}
        mentorName="Sarah Lee"
        menteeName="Henry Zhang"
        editor={editor}
      />
      <MeetingLogEditButtons editor={editor} />
    </>
  );
};

describe("MeetingLogTable", () => {
  it("renders one row per meeting, numbered from 1, with Pacific times", () => {
    render(
      <MeetingLogTable
        meetings={[meeting(), meeting({ meetingId: "gm-80-2" })]}
        mentorName="Sarah Lee"
        menteeName="Henry Zhang"
      />,
    );
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    // Header row plus two meetings.
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText("1")).toBeInTheDocument();
    expect(
      within(rows[1]).getByText("2024-03-01 · 15:30 - 16:30"),
    ).toBeInTheDocument();
  });

  it("names the mentee in a mentee-absent tag", () => {
    render(
      <MeetingLogTable
        meetings={[meeting({ isCompleted: false, note: ["mentee_absent"] })]}
        mentorName="Sarah Lee"
        menteeName="Henry Zhang"
      />,
    );
    expect(screen.getByText(/Henry Zhang/)).toBeInTheDocument();
  });

  it("without an editor, shows no selection checkboxes", () => {
    render(
      <MeetingLogTable
        meetings={[meeting()]}
        mentorName="Sarah Lee"
        menteeName="Henry Zhang"
      />,
    );
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("in edit mode, shows a delete checkbox per row and in the header", async () => {
    render(<Harness meetings={[meeting()]} />);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(
      screen.getByRole("checkbox", {
        name: "Select all meetings for deletion",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Select meeting 1 for deletion" }),
    ).toBeInTheDocument();
  });
});

describe("useMeetingLogEditor", () => {
  it("sends only deletes for a delete confirmation and leaves edit mode", async () => {
    const onSave = vi.fn().mockResolvedValue();
    const { result } = renderHook(() =>
      useMeetingLogEditor({ meetings: [meeting()], onSave }),
    );
    act(() => result.current.startEditing());
    act(() => result.current.togglePendingDelete("gm-80-1", true));
    act(() => result.current.setConfirmAction("delete"));
    await act(() => result.current.handleConfirm());

    expect(onSave).toHaveBeenCalledWith({ updates: [], deletes: ["gm-80-1"] });
    expect(result.current.isEditing).toBe(false);
    expect(result.current.confirmAction).toBe(null);
  });

  it("on failure, toasts the server message and keeps the pending edits", async () => {
    const onSave = vi
      .fn()
      .mockRejectedValue({ response: { data: { message: "Round has ended" } } });
    const { result } = renderHook(() =>
      useMeetingLogEditor({ meetings: [meeting()], onSave }),
    );
    act(() => result.current.startEditing());
    act(() => result.current.patchField("gm-80-1", { isCompleted: false }));
    act(() => result.current.setConfirmAction("update"));
    await act(() => result.current.handleConfirm());

    expect(toast.error).toHaveBeenCalledWith("Round has ended");
    expect(result.current.isEditing).toBe(true);
    expect(result.current.updateCount).toBe(1);
  });
});
