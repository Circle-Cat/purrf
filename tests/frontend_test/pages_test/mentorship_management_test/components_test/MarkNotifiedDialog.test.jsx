import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import MarkNotifiedDialog from "@/pages/MentorshipManagement/components/email/MarkNotifiedDialog";
import { stagesForList } from "@/pages/MentorshipManagement/components/email/emailLabels";
import { markNotified } from "@/api/mentorshipEmailApi";

vi.mock("@/api/mentorshipEmailApi", () => ({ markNotified: vi.fn() }));

// Distinct ids, names and reached stages, so a swapped read shows up.
const ann = { userId: 22, name: "Ann Lee", notifiedStages: ["admission"] };
const bo = { userId: 23, name: "Bo Park", notifiedStages: [] };
const cy = {
  userId: 31,
  name: "Cy Ruiz",
  notifiedStages: ["admission", "match_result"],
};

const renderDialog = (props = {}) => {
  const onMarked = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <MarkNotifiedDialog
      open
      onOpenChange={onOpenChange}
      roundId={7}
      people={[ann, bo, cy]}
      stageOptions={stagesForList(false)}
      onMarked={onMarked}
      {...props}
    />,
  );
  return { onMarked, onOpenChange };
};

const choose = (value) =>
  userEvent.selectOptions(screen.getByLabelText("Which notification"), value);
const write = (text) =>
  userEvent.type(screen.getByLabelText("How it was sent"), text);
const markButton = () =>
  screen.getByRole("button", { name: /^Mark as notified · \d+$/ });

describe("MarkNotifiedDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
  });

  it("names one person in the title and marks the stages already reached", () => {
    renderDialog({ people: [ann] });

    expect(screen.getByText("Mark as notified — Ann Lee")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Purrf did not send this one, so this note is the only record that it went out — say where and when. This cannot be undone.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: "Admission & onboarding (already notified)",
      }),
    ).toBeDisabled();
    expect(screen.getByRole("option", { name: "Match result" })).toBeEnabled();
    expect(
      screen.queryByRole("option", { name: /New round invitation/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("How it was sent")).toHaveAttribute(
      "placeholder",
      "Sent on Teams. No reply yet.",
    );
  });

  it("counts who a batch will skip for the stage picked", async () => {
    renderDialog();
    expect(screen.getByText("Mark 3 people as notified")).toBeInTheDocument();

    await choose("admission");
    await write("Sent on Teams");

    expect(
      screen.getByText(
        "2 of 3 already notified for this stage — they will be skipped",
      ),
    ).toBeInTheDocument();
    expect(markButton()).toHaveTextContent("Mark as notified · 1");
    expect(markButton()).toBeEnabled();
  });

  it("will not mark when everyone already has the stage", async () => {
    renderDialog({ people: [ann, cy] });
    await choose("admission");
    await write("Sent on Teams");

    expect(markButton()).toHaveTextContent("Mark as notified · 0");
    expect(markButton()).toBeDisabled();
  });

  it("will not mark with a blank note", async () => {
    renderDialog();
    await choose("match_result");
    await write("   ");

    expect(markButton()).toHaveTextContent("Mark as notified · 2");
    expect(markButton()).toBeDisabled();
  });

  it("sends everyone picked with the note trimmed, then says how many were marked", async () => {
    const result = {
      marked: [23],
      skipped: [
        { userId: 22, reason: "already_notified" },
        { userId: 31, reason: "already_notified" },
      ],
    };
    markNotified.mockResolvedValue(result);
    const { onMarked, onOpenChange } = renderDialog();
    await choose("admission");
    await write("  Sent on Teams, 10-10.  ");

    await userEvent.click(markButton());

    await waitFor(() =>
      expect(markNotified).toHaveBeenCalledWith(7, {
        userIds: [22, 23, 31],
        stage: "admission",
        body: "Sent on Teams, 10-10.",
      }),
    );
    expect(toast.success).toHaveBeenCalledWith(
      "Marked 1 as notified, 2 skipped",
    );
    expect(onMarked).toHaveBeenCalledWith(result);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("on failure toasts the server's message and keeps the note", async () => {
    markNotified.mockRejectedValue({
      response: {
        data: {
          message:
            "Notifications can only be marked while the round is in progress.",
        },
      },
    });
    const { onMarked } = renderDialog({ people: [bo] });
    await choose("match_result");
    await write("Called her");

    await userEvent.click(markButton());

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Notifications can only be marked while the round is in progress.",
      ),
    );
    expect(screen.getByLabelText("How it was sent")).toHaveValue("Called her");
    expect(onMarked).not.toHaveBeenCalled();
  });
});
