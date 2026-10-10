import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import NoteTimeline from "@/pages/MentorshipManagement/components/NoteTimeline";
import { addParticipantNote } from "@/api/mentorshipApi";
import { stagesForList } from "@/pages/MentorshipManagement/components/email/emailLabels";
import { noteOf } from "../participantDetail.helper";

vi.mock("@/api/mentorshipApi", () => ({ addParticipantNote: vi.fn() }));
vi.mock("@/api/mentorshipEmailApi", () => ({ markNotified: vi.fn() }));

const renderTimeline = (props = {}) =>
  render(
    <NoteTimeline
      notes={[]}
      roundId={7}
      userId={3104}
      canAdd
      onAdded={vi.fn()}
      {...props}
    />,
  );

describe("NoteTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(toast, "error").mockImplementation(() => {});
  });

  it("labels a note that marked someone notified with its stage", () => {
    renderTimeline({
      notes: [
        noteOf({
          noteId: 6,
          tag: "notified",
          notificationStage: "match_result",
          body: "Sent on Teams",
        }),
      ],
    });
    expect(
      screen.getByText("Marked as notified: Match result"),
    ).toBeInTheDocument();
    expect(screen.getByText("Sent on Teams")).toBeInTheDocument();
  });

  it("offers Mark as notified only where it may and the timeline can be added to", () => {
    const { unmount } = renderTimeline({
      canMarkNotified: false,
      personName: "Alice Chen",
      markStageOptions: stagesForList(false),
    });
    expect(
      screen.queryByRole("button", { name: "Mark as notified" }),
    ).not.toBeInTheDocument();
    unmount();

    renderTimeline({
      canAdd: false,
      canMarkNotified: true,
      personName: "Alice Chen",
      markStageOptions: stagesForList(false),
    });
    expect(
      screen.queryByRole("button", { name: "Mark as notified" }),
    ).not.toBeInTheDocument();
  });

  it("opens Mark as notified for the person, with the stages already reached", async () => {
    renderTimeline({
      canMarkNotified: true,
      personName: "Alice Chen",
      markStageOptions: stagesForList(false),
      notifiedStages: ["match_result"],
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Mark as notified" }),
    );

    expect(
      await screen.findByText("Mark as notified — Alice Chen"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Match result (already notified)" }),
    ).toBeDisabled();
  });

  it("says so when there are no notes", () => {
    renderTimeline();
    expect(screen.getByText("No notes yet.")).toBeInTheDocument();
  });

  it("lists notes in the order given, with author, time and body", () => {
    renderTimeline({
      notes: [
        noteOf({
          noteId: 2,
          body: "Second",
          author: { userId: 12, name: "Eve Ko" },
        }),
        noteOf({ noteId: 1, body: "First" }),
      ],
    });
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Second");
    expect(items[0]).toHaveTextContent("Eve Ko");
    expect(items[1]).toHaveTextContent("First");
    expect(items[1]).toHaveTextContent("Dana Wu");
  });

  it("names the author without an ID, and falls back to the ID alone", () => {
    renderTimeline({
      notes: [
        noteOf({ noteId: 2, author: { userId: 12, name: "Eve Ko" } }),
        noteOf({ noteId: 1, author: { userId: 31, name: null } }),
      ],
    });
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Eve Ko ·");
    expect(items[0]).not.toHaveTextContent("ID 12");
    expect(items[1]).toHaveTextContent("User 31 ·");
  });

  it("labels tagged notes and marks the ones an approval wrote", () => {
    renderTimeline({
      notes: [
        noteOf({ noteId: 3, tag: "matching_exemption", requestId: 40 }),
        noteOf({ noteId: 4, tag: "status_change" }),
        noteOf({ noteId: 5, tag: null }),
      ],
    });
    expect(screen.getByText("Exemption")).toBeInTheDocument();
    expect(screen.getByText("Status change")).toBeInTheDocument();
    expect(screen.getAllByText("(via approval)")).toHaveLength(1);
  });

  it("puts notifications among the notes by time, saying how each went", () => {
    renderTimeline({
      notes: [
        noteOf({
          noteId: 2,
          body: "Newer note",
          createdAt: "2026-10-05T18:00:00Z",
        }),
        noteOf({
          noteId: 1,
          body: "Older note",
          createdAt: "2026-09-01T18:00:00Z",
        }),
      ],
      sends: [
        {
          sendId: 14,
          stage: "match_result",
          subject: "Your match",
          delivered: true,
          reason: null,
          at: "2026-10-12T16:00:00Z",
        },
        {
          sendId: 11,
          stage: "admission",
          subject: "Welcome aboard",
          delivered: false,
          reason: "Not handed to Kit: unsubscribed",
          at: "2026-09-20T17:00:00Z",
        },
      ],
    });
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      "NotificationKit · 2026-10-12 09:00Match result · Your matchSent",
      expect.stringContaining("Newer note"),
      "NotificationKit · 2026-09-20 10:00Admission & onboarding · Welcome aboardNot sent. Not handed to Kit: unsubscribed",
      expect.stringContaining("Older note"),
    ]);
  });

  it("offers no Add a note when it cannot add", () => {
    renderTimeline({ canAdd: false });
    expect(
      screen.queryByRole("button", { name: "Add a note" }),
    ).not.toBeInTheDocument();
  });

  it("will not send a blank note", async () => {
    renderTimeline();
    await userEvent.click(screen.getByRole("button", { name: "Add a note" }));
    await userEvent.type(screen.getByLabelText("Note"), "   ");
    expect(screen.getByRole("button", { name: "Save note" })).toBeDisabled();
  });

  it("sends the note trimmed, closes, and tells the page", async () => {
    addParticipantNote.mockResolvedValue({ data: noteOf() });
    const onAdded = vi.fn();
    renderTimeline({ onAdded });

    await userEvent.click(screen.getByRole("button", { name: "Add a note" }));
    await userEvent.type(screen.getByLabelText("Note"), "  Called her today  ");
    await userEvent.click(screen.getByRole("button", { name: "Save note" }));

    await waitFor(() =>
      expect(addParticipantNote).toHaveBeenCalledWith(
        7,
        3104,
        "Called her today",
      ),
    );
    expect(onAdded).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByLabelText("Note")).not.toBeInTheDocument(),
    );
  });

  it("labels marks and names the partner of the pair a note is about", () => {
    renderTimeline({
      pairs: [
        {
          pairId: 80,
          partner: { firstName: "Bob", lastName: "Smith", preferredName: null },
        },
      ],
      notes: [
        noteOf({ noteId: 3, tag: "red_flag", pairId: null, body: "Flag" }),
        noteOf({
          noteId: 2,
          tag: "no_show",
          pairId: 80,
          body: "Missed both calls",
        }),
      ],
    });
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Red flag");
    expect(items[0]).not.toHaveTextContent("with");
    expect(items[1]).toHaveTextContent("No show");
    expect(items[1]).toHaveTextContent("with Bob Smith");
  });

  it("on failure toasts the server's message and keeps the text", async () => {
    addParticipantNote.mockRejectedValue({
      response: { data: { message: "Mentorship round 7 is not in progress." } },
    });
    renderTimeline();

    await userEvent.click(screen.getByRole("button", { name: "Add a note" }));
    await userEvent.type(screen.getByLabelText("Note"), "Late again");
    await userEvent.click(screen.getByRole("button", { name: "Save note" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Mentorship round 7 is not in progress.",
      ),
    );
    expect(screen.getByLabelText("Note")).toHaveValue("Late again");
  });
});
