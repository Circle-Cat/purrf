import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import NoteTimeline from "@/pages/MentorshipManagement/components/NoteTimeline";
import { addParticipantNote } from "@/api/mentorshipApi";
import { noteOf } from "../participantDetail.helper";

vi.mock("@/api/mentorshipApi", () => ({ addParticipantNote: vi.fn() }));

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
