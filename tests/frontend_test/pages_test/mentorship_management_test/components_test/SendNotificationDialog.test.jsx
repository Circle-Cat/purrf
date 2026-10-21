import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SendNotificationDialog from "@/pages/MentorshipManagement/components/email/SendNotificationDialog";
import { pacificToUtcIso } from "@/pages/MentorshipManagement/components/email/sendTime";
import * as api from "@/api/mentorshipEmailApi";

vi.mock("@/api/mentorshipEmailApi", () => ({
  listKitDrafts: vi.fn(),
  markNotified: vi.fn(),
  createEmailSend: vi.fn(),
  refreshEmailPreview: vi.fn(),
  confirmEmailSend: vi.fn(),
  cancelEmailSend: vi.fn(),
}));

const DRAFTS = [
  { id: 900, subject: "Sign up for Fall", createdAt: "2026-10-01T00:00:00Z" },
  { id: 901, subject: "Your match", createdAt: "2026-10-02T00:00:00Z" },
];

const RECIPIENTS = [
  { userId: 11, name: "Alice Doe" },
  { userId: 12, name: "Bob Smith" },
];

const send = (over = {}) => ({
  sendId: 5,
  roundId: 7,
  stage: "match_result",
  kitDraftId: 901,
  kitDraftSubject: "Your match",
  status: "draft",
  senderAddress: "notification-test@circlecat.org",
  counts: { pending: 2 },
  ...over,
});

const preview = (over = {}) => ({
  subject: "Your match",
  html: "<p>Oct 20</p>",
  senderAddress: "notification-test@circlecat.org",
  filterOk: true,
  recipientCount: 2,
  invalidHrefs: [],
  noEmail: [],
  recentlySentUserIds: [],
  previewToken: "tok",
  ...over,
});

const renderDialog = (props = {}) => {
  const handlers = { onOpenChange: vi.fn(), onScheduled: vi.fn() };
  render(
    <SendNotificationDialog
      open
      roundId="7"
      recipients={RECIPIENTS}
      {...handlers}
      {...props}
    />,
  );
  return handlers;
};

const pickAndCreate = async () => {
  await screen.findByRole("option", { name: "Your match" });
  await userEvent.selectOptions(screen.getByLabelText("Stage"), "match_result");
  await userEvent.selectOptions(screen.getByLabelText("Kit draft"), "901");
  await userEvent.click(screen.getByRole("button", { name: "Create" }));
};

const setSendTime = async (date, time) => {
  const dateInput = screen.getByLabelText("Send date");
  const timeInput = screen.getByLabelText("Send time");
  await userEvent.clear(dateInput);
  await userEvent.type(dateInput, date);
  await userEvent.clear(timeInput);
  await userEvent.type(timeInput, time);
};

describe("SendNotificationDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listKitDrafts.mockResolvedValue(DRAFTS);
    api.createEmailSend.mockResolvedValue(send());
    api.refreshEmailPreview.mockResolvedValue(preview());
    api.confirmEmailSend.mockResolvedValue(send({ status: "preparing" }));
    api.cancelEmailSend.mockResolvedValue(send({ status: "cancelled" }));
  });

  it("lists the picked people and the Kit drafts by subject", async () => {
    renderDialog();
    expect(screen.getByText("To 2 people")).toBeInTheDocument();
    expect(screen.getByText("Alice Doe, Bob Smith")).toBeInTheDocument();
    expect(
      await screen.findByRole("option", { name: "Sign up for Fall" }),
    ).toBeInTheDocument();
  });

  it("turns off drafts Kit cannot send and says why", async () => {
    api.listKitDrafts.mockResolvedValue([
      ...DRAFTS,
      {
        id: 902,
        subject: "Old invite",
        createdAt: "2026-09-01T00:00:00Z",
        problem: "links Kit cannot send: 'circlecat.org'",
      },
    ]);
    renderDialog();

    const bad = await screen.findByRole("option", {
      name: "Old invite — can't send: links Kit cannot send: 'circlecat.org'",
    });
    expect(bad).toBeDisabled();
    expect(screen.getByRole("option", { name: "Your match" })).toBeEnabled();
  });

  it("starts on the given stage", async () => {
    renderDialog({ defaultStage: "round_recruitment" });
    expect(screen.getByLabelText("Stage")).toHaveValue("round_recruitment");
  });

  it("needs a stage and a draft before Create", async () => {
    renderDialog();
    await screen.findByRole("option", { name: "Your match" });
    const create = screen.getByRole("button", { name: "Create" });
    expect(create).toBeDisabled();
    await userEvent.selectOptions(
      screen.getByLabelText("Stage"),
      "match_result",
    );
    expect(create).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Kit draft"), "901");
    expect(create).toBeEnabled();
  });

  it("blocks Create while a draft's error shows, until another draft is picked", async () => {
    api.createEmailSend.mockRejectedValueOnce({
      response: {
        data: { message: "This Kit draft has links Kit cannot send." },
      },
    });
    renderDialog();
    await pickAndCreate();

    expect(
      await screen.findByText("This Kit draft has links Kit cannot send."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText("Kit draft"), "900");

    expect(
      screen.queryByText("This Kit draft has links Kit cannot send."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeEnabled();
  });

  it("creates the send for the picked people and shows its preview", async () => {
    renderDialog();
    await pickAndCreate();
    expect(api.createEmailSend).toHaveBeenCalledWith({
      roundId: 7,
      stage: "match_result",
      kitDraftId: 901,
      userIds: [11, 12],
    });
    expect(await screen.findByTitle("Email preview")).toHaveAttribute(
      "sandbox",
      "",
    );
    expect(api.refreshEmailPreview).toHaveBeenCalledWith(5);
    expect(screen.getByText("Match result · Your match")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create" })).toBeNull();
  });

  it("shows the preview checks", async () => {
    api.refreshEmailPreview.mockResolvedValue(
      preview({
        filterOk: false,
        invalidHrefs: ["htp://bad"],
        recentlySentUserIds: [11],
        noEmail: [{ userId: 12 }],
      }),
    );
    renderDialog();
    await pickAndCreate();
    await screen.findByTitle("Email preview");
    expect(
      screen.getByText(
        "The recipients or sender of this draft were changed in Kit.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("htp://bad")).toBeInTheDocument();
    expect(
      screen.getByText(/1 of them already got a Match result email/),
    ).toBeInTheDocument();
    expect(screen.getByText("No email address for user 12.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  it("offers the preview again when it fails", async () => {
    api.refreshEmailPreview.mockRejectedValueOnce(new Error("Kit is down"));
    renderDialog();
    await pickAndCreate();
    expect(await screen.findByRole("alert")).toHaveTextContent("Kit is down");
    await userEvent.click(
      screen.getByRole("button", { name: "Try the preview again" }),
    );
    expect(await screen.findByTitle("Email preview")).toBeInTheDocument();
    expect(api.refreshEmailPreview).toHaveBeenCalledTimes(2);
  });

  it("confirms the Pacific time typed with the preview token", async () => {
    const { onScheduled, onOpenChange } = renderDialog();
    await pickAndCreate();
    await screen.findByTitle("Email preview");
    await setSendTime("2030-10-20", "09:00");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(api.confirmEmailSend).toHaveBeenCalledWith(5, {
      sendAt: "2030-10-20T16:00:00Z",
      previewToken: "tok",
    });
    await waitFor(() =>
      expect(onScheduled).toHaveBeenCalledWith("2030-10-20T16:00:00Z"),
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(api.cancelEmailSend).not.toHaveBeenCalled();
  });

  it("stays open with the error when Confirm fails", async () => {
    api.confirmEmailSend.mockRejectedValue({
      response: { data: { message: "Preview is out of date" } },
    });
    const { onScheduled, onOpenChange } = renderDialog();
    await pickAndCreate();
    await screen.findByTitle("Email preview");
    await setSendTime("2030-10-20", "09:00");
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Preview is out of date",
    );
    expect(onScheduled).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("blocks a send time less than 30 minutes away", async () => {
    renderDialog();
    await pickAndCreate();
    await screen.findByTitle("Email preview");
    await setSendTime("2020-01-01", "09:00");
    expect(
      screen.getByText("Pick a time at least 30 minutes from now."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  it("cancels the created send when closed without confirming", async () => {
    const { onOpenChange } = renderDialog();
    await pickAndCreate();
    await screen.findByTitle("Email preview");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.cancelEmailSend).toHaveBeenCalledWith(5);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("only logs a failed cancel", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    api.cancelEmailSend.mockRejectedValue(new Error("gone"));
    const { onOpenChange } = renderDialog();
    await pickAndCreate();
    await screen.findByTitle("Email preview");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(screen.queryByRole("alert")).toBeNull();
    error.mockRestore();
  });

  it("has nothing to cancel when closed before Create", async () => {
    const { onOpenChange } = renderDialog();
    await screen.findByRole("option", { name: "Your match" });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.cancelEmailSend).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("reads the send time as Pacific Time, across daylight saving", () => {
    // PDT (UTC-7) before 1 Nov 2026, PST (UTC-8) after.
    expect(pacificToUtcIso("2026-10-20", "09:00")).toBe("2026-10-20T16:00:00Z");
    expect(pacificToUtcIso("2026-11-10", "09:00")).toBe("2026-11-10T17:00:00Z");
  });
});
