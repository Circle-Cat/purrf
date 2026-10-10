import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import EmailConversation from "@/components/email/EmailConversation";
import { conversationOf, messageOf, threadOf } from "./email.helper";

const older = threadOf({
  threadId: 40,
  subject: "Older",
  needsReply: false,
  messages: [
    messageOf({
      messageId: 400,
      gmailInternalDate: "2026-09-01T16:00:00Z",
      createdAt: "2026-09-01T16:00:05Z",
    }),
  ],
});

const renderConversation = (props = {}) =>
  render(
    <EmailConversation
      conversation={conversationOf({ threads: [older, threadOf()] })}
      formatTime={(iso) => iso}
      canSend
      onCompose={vi.fn()}
      onReply={vi.fn()}
      {...props}
    />,
  );

describe("EmailConversation", () => {
  it("lists conversations newest activity first", () => {
    renderConversation();
    // The title element also holds the "Needs reply" badge; read only its own text node.
    expect(
      screen
        .getAllByText(/^(Checking in|Older)$/)
        .map((el) => el.firstChild.textContent),
    ).toEqual(["Checking in", "Older"]);
  });

  it("says No emails yet. when there are none", () => {
    renderConversation({ conversation: conversationOf({ threads: [] }) });
    expect(screen.getByText("No emails yet.")).toBeInTheDocument();
  });

  it("tolerates a missing conversation", () => {
    renderConversation({ conversation: null });
    expect(screen.getByText("No emails yet.")).toBeInTheDocument();
  });

  it("is read-only without canSend", () => {
    renderConversation({ canSend: false });
    expect(
      screen.queryByRole("button", { name: "Send email" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reply" }),
    ).not.toBeInTheDocument();
  });

  it("keeps Send email and Reply disabled and titled with a hint", () => {
    renderConversation({ sendDisabledHint: "Needs the grant" });
    for (const button of [
      screen.getByRole("button", { name: "Send email" }),
      ...screen.getAllByRole("button", { name: "Reply" }),
    ]) {
      expect(button).toBeDisabled();
      expect(button).toHaveAttribute("title", "Needs the grant");
    }
  });

  it("opens compose and reply", async () => {
    const onCompose = vi.fn();
    const onReply = vi.fn();
    renderConversation({ onCompose, onReply });
    await userEvent.click(screen.getByRole("button", { name: "Send email" }));
    expect(onCompose).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getAllByRole("button", { name: "Reply" })[0]);
    expect(onReply).toHaveBeenCalledWith(threadOf());
  });
});
