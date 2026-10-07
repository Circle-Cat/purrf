import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { toast } from "sonner";
import InboxPage from "@/pages/Inbox";
import * as api from "@/api/inboxApi";

vi.mock("@/api/inboxApi", () => ({
  listInboxThreads: vi.fn(),
  getInboxCount: vi.fn(),
  getInboxThread: vi.fn(),
  replyToInboxThread: vi.fn(),
  archiveInboxThread: vi.fn(),
  unarchiveInboxThread: vi.fn(),
  assignInboxThread: vi.fn(),
  unassignInboxThread: vi.fn(),
  moveInboxThread: vi.fn(),
  getInboxAssignOptions: vi.fn(),
  searchInboxPeople: vi.fn(),
  inboxAttachmentUrl: (id, messageId, index) =>
    `http://api.test/inbox/threads/${id}/messages/${messageId}/attachments/${index}`,
}));

const row = (over = {}) => ({
  threadId: 1,
  service: "mentorship",
  subject: "Question about meeting cadence",
  snippet: "How often should we meet?",
  lastActivityAt: "2026-09-29T21:14:00Z",
  sender: "wang@example.com",
  person: { userId: 7, name: "Wang Xiao" },
  matchedBy: "primary",
  needsReply: true,
  archived: false,
  unassigned: true,
  noMatchingUser: false,
  machineTag: null,
  assignment: null,
  movedFrom: null,
  ...over,
});

const message = (over = {}) => ({
  messageId: 11,
  direction: "inbound",
  from: "wang@example.com",
  to: "mentorship@circlecat.org",
  at: "2026-09-29T21:14:00Z",
  bodyHtml: null,
  bodyText: "How often should we meet?",
  inboundKind: null,
  attachments: [],
  sentByName: null,
  ...over,
});

const detail = (over = {}) => ({
  ...row(),
  messages: [message()],
  latestMessageId: 11,
  replyAlias: "mentorship@circlecat.org",
  canAssign: true,
  canMove: true,
  tracked: false,
  openBounce: null,
  movedAt: null,
  ...over,
});

const listData = (threads, over = {}) => ({
  data: {
    threads,
    counts: { needsReply: 2, unassigned: 1 },
    services: [
      { key: "mentorship", needsReply: 1 },
      { key: "recruiting", needsReply: 1 },
      { key: "inquiries", needsReply: 0 },
    ],
    ...over,
  },
});

const renderAt = (url = "/inbox") => {
  const router = createMemoryRouter(
    [{ path: "/inbox", element: <InboxPage /> }],
    { initialEntries: [url] },
  );
  render(<RouterProvider router={router} />);
  return router;
};

const lastListParams = () => api.listInboxThreads.mock.calls.at(-1)[0];
const thread = () => screen.findByRole("region", { name: "Thread" });
const open = (subject) =>
  fireEvent.click(
    screen.getByRole("button", { name: `Open thread ${subject}` }),
  );

let errorSpy;

beforeEach(() => {
  vi.resetAllMocks();
  errorSpy = vi.spyOn(toast, "error").mockImplementation(() => {});
  api.listInboxThreads.mockResolvedValue(listData([row()]));
  api.getInboxThread.mockResolvedValue({ data: detail() });
});

afterEach(() => vi.restoreAllMocks());

describe("InboxPage list", () => {
  it("renders rows from the API with service chips and counts", async () => {
    renderAt();
    expect(
      await screen.findByRole("button", {
        name: "Open thread Question about meeting cadence",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Wang Xiao/)).toBeInTheDocument();
    const services = screen.getByRole("group", { name: "Services" });
    expect(within(services).getByRole("button", { name: /^All/ })).toBeTruthy();
    expect(
      within(services).getByRole("button", { name: /^Recruiting/ }),
    ).toHaveTextContent("1");
    expect(lastListParams()).toEqual({});
  });

  it("writes the service filter to the URL and refetches", async () => {
    const router = renderAt();
    fireEvent.click(
      await within(
        await screen.findByRole("group", { name: "Services" }),
      ).findByRole("button", { name: /^Recruiting/ }),
    );
    await waitFor(() =>
      expect(lastListParams()).toEqual({ service: "recruiting" }),
    );
    expect(router.state.location.search).toBe("?service=recruiting");
  });

  it("reads the service filter from the URL", async () => {
    renderAt("/inbox?service=inquiries");
    await waitFor(() =>
      expect(api.listInboxThreads).toHaveBeenCalledWith({
        service: "inquiries",
      }),
    );
  });

  it("passes the chip filters, archived toggle and search to the API", async () => {
    renderAt();
    await screen.findByRole("group", { name: "Filters" });
    const filters = screen.getByRole("group", { name: "Filters" });
    fireEvent.click(
      within(filters).getByRole("button", { name: /^Needs reply/ }),
    );
    await waitFor(() => expect(lastListParams()).toEqual({ needsReply: true }));
    fireEvent.click(
      within(filters).getByRole("button", { name: /^Unassigned/ }),
    );
    await waitFor(() =>
      expect(lastListParams()).toEqual({ needsReply: true, unassigned: true }),
    );
    fireEvent.click(screen.getByLabelText("Show archived"));
    await waitFor(() => expect(lastListParams().archived).toBe(true));
    fireEvent.change(screen.getByLabelText("Search threads"), {
      target: { value: " wang " },
    });
    await waitFor(() => expect(lastListParams().q).toBe("wang"));
  });

  it("shows machine, archived, moved and assignment tags from row fields", async () => {
    api.listInboxThreads.mockResolvedValue(
      listData([
        row({
          machineTag: "bounce",
          archived: true,
          needsReply: false,
          unassigned: false,
          movedFrom: "inquiries",
          assignment: { kind: "round", roundId: 3, roundName: "Fall 2026" },
        }),
        row({
          threadId: 2,
          subject: "Interview",
          person: null,
          noMatchingUser: true,
          sender: "who@example.com",
          assignment: {
            kind: "application",
            applicationId: 9,
            jobTitle: "Engineer",
          },
        }),
      ]),
    );
    renderAt();
    await screen.findByRole("button", { name: /Open thread Interview/ });
    const first = screen
      .getByRole("button", { name: /Open thread Question/ })
      .closest("li");
    for (const text of [
      "Delivery failed",
      "Archived",
      "Moved from Inquiries",
      "Fall 2026 round",
    ]) {
      expect(first).toHaveTextContent(text);
    }
    const second = screen
      .getByRole("button", { name: /Open thread Interview/ })
      .closest("li");
    expect(second).toHaveTextContent("No matching user");
    expect(second).toHaveTextContent("Engineer");
  });
});

describe("InboxPage thread detail", () => {
  it("sanitizes the HTML body and links attachments", async () => {
    api.getInboxThread.mockResolvedValue({
      data: detail({
        messages: [
          message({
            bodyHtml: '<p>Hello</p><img src=x onerror="alert(1)">',
            attachments: [
              { name: "cv.pdf", size: 2048, attachmentId: "a1" },
              { name: "b.png", size: 10, attachmentId: "a2" },
            ],
          }),
        ],
      }),
    });
    renderAt();
    await screen.findByText("Question about meeting cadence", {
      selector: "span",
    });
    open("Question about meeting cadence");
    const pane = await thread();
    await within(pane).findByText("Hello");
    expect(pane.innerHTML).not.toContain("onerror");
    const cv = within(pane).getByRole("link", { name: /cv\.pdf/ });
    expect(cv).toHaveAttribute(
      "href",
      "http://api.test/inbox/threads/1/messages/11/attachments/0",
    );
    expect(cv).toHaveAttribute("target", "_blank");
    expect(cv).toHaveAttribute("rel", "noopener noreferrer");
    expect(cv).toHaveAttribute("download");
    expect(within(pane).getByRole("link", { name: /b\.png/ })).toHaveAttribute(
      "href",
      "http://api.test/inbox/threads/1/messages/11/attachments/1",
    );
  });

  it("hides Assign when canAssign is false and Move when canMove is false", async () => {
    api.getInboxThread.mockResolvedValue({
      data: detail({ canAssign: false, canMove: false }),
    });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    await within(pane).findByRole("button", { name: "Archive" });
    expect(within(pane).queryByRole("button", { name: "Assign" })).toBeNull();
    expect(within(pane).queryByLabelText("Move to")).toBeNull();
  });

  it("lists only the other two services in Move and moves the thread", async () => {
    api.moveInboxThread.mockResolvedValue({
      data: detail({ service: "recruiting", movedFrom: "mentorship" }),
    });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    const select = await within(pane).findByLabelText("Move to");
    const options = within(select)
      .getAllByRole("option")
      .map((o) => o.value);
    expect(options).toEqual(["", "recruiting", "inquiries"]);
    fireEvent.change(select, { target: { value: "recruiting" } });
    fireEvent.click(within(pane).getByRole("button", { name: "Move" }));
    await waitFor(() =>
      expect(api.moveInboxThread).toHaveBeenCalledWith(1, "recruiting"),
    );
  });

  it("clears the selection when the thread is no longer visible after Move", async () => {
    api.moveInboxThread.mockResolvedValue({ data: detail() });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    const select = await within(pane).findByLabelText("Move to");
    api.getInboxThread.mockRejectedValue({
      response: { status: 400 },
      message: "not found",
    });
    const before = api.listInboxThreads.mock.calls.length;
    fireEvent.change(select, { target: { value: "inquiries" } });
    fireEvent.click(within(pane).getByRole("button", { name: "Move" }));
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Thread" })).toBeNull(),
    );
    expect(api.listInboxThreads.mock.calls.length).toBeGreaterThan(before);
  });

  it("closes the thread when Move returns no data", async () => {
    api.moveInboxThread.mockResolvedValue({ data: null });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    const select = await within(pane).findByLabelText("Move to");
    api.getInboxThread.mockRejectedValue({
      response: { status: 400 },
      message: "not found",
    });
    const before = api.listInboxThreads.mock.calls.length;
    fireEvent.change(select, { target: { value: "inquiries" } });
    fireEvent.click(within(pane).getByRole("button", { name: "Move" }));
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Thread" })).toBeNull(),
    );
    expect(api.listInboxThreads.mock.calls.length).toBeGreaterThan(before);
  });

  it("archives and notifies the sidebar", async () => {
    const listener = vi.fn();
    window.addEventListener("inbox:changed", listener);
    api.archiveInboxThread.mockResolvedValue({
      data: detail({ archived: true }),
    });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    fireEvent.click(
      await within(pane).findByRole("button", { name: "Archive" }),
    );
    expect(
      await within(pane).findByRole("button", { name: "Unarchive" }),
    ).toBeInTheDocument();
    expect(listener).toHaveBeenCalled();
    window.removeEventListener("inbox:changed", listener);
  });

  it("removes an assignment through the dialog", async () => {
    const assigned = detail({
      unassigned: false,
      assignment: { kind: "round", roundId: 4, roundName: "Spring 2026" },
    });
    api.getInboxThread.mockResolvedValue({ data: assigned });
    api.getInboxAssignOptions.mockResolvedValue({ data: { rounds: [] } });
    api.unassignInboxThread.mockResolvedValue({
      data: detail({ unassigned: true }),
    });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    fireEvent.click(
      await within(pane).findByRole("button", { name: "Reassign" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Remove assignment" }),
    );
    await waitFor(() =>
      expect(api.unassignInboxThread).toHaveBeenCalledWith(1),
    );
    expect(
      await within(pane).findByRole("button", { name: "Assign" }),
    ).toBeInTheDocument();
  });

  it("ignores a write response for a thread that is no longer open", async () => {
    api.listInboxThreads.mockResolvedValue(
      listData([row(), row({ threadId: 2, subject: "Other thread" })]),
    );
    api.getInboxThread.mockImplementation((id) =>
      Promise.resolve({
        data:
          id === 1
            ? detail()
            : detail({ threadId: 2, subject: "Other thread" }),
      }),
    );
    let finish;
    api.archiveInboxThread.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    fireEvent.click(
      await within(pane).findByRole("button", { name: "Archive" }),
    );
    open("Other thread");
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Other thread" }),
      ).toBeInTheDocument(),
    );
    finish({ data: detail({ archived: true }) });
    await waitFor(() =>
      expect(api.archiveInboxThread).toHaveBeenCalledTimes(1),
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(
      screen.getByRole("heading", { name: "Other thread" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Question about meeting cadence" }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: "Archive" })).toBeEnabled();
  });

  it("disables Send while a reply is pending so it posts once", async () => {
    let finish;
    api.replyToInboxThread.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    fireEvent.change(await within(pane).findByLabelText("Reply"), {
      target: { value: "hi" },
    });
    const send = within(pane).getByRole("button", { name: "Send reply" });
    fireEvent.click(send);
    fireEvent.click(send);
    expect(send).toBeDisabled();
    expect(api.replyToInboxThread).toHaveBeenCalledTimes(1);
    finish({ data: detail({ latestMessageId: 12 }) });
    await waitFor(() =>
      expect(within(pane).getByLabelText("Reply")).toHaveValue(""),
    );
  });

  it("disables the reply box when the environment has no alias", async () => {
    api.getInboxThread.mockResolvedValue({
      data: detail({ replyAlias: null }),
    });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    expect(
      await within(pane).findByText(
        "This environment has no alias for this inbox",
      ),
    ).toBeInTheDocument();
    expect(within(pane).getByLabelText("Reply")).toBeDisabled();
  });

  it("sends the reply as escaped HTML with lastSeenMessageId", async () => {
    api.replyToInboxThread.mockResolvedValue({
      data: detail({
        latestMessageId: 12,
        messages: [
          message(),
          message({ messageId: 12, direction: "outbound" }),
        ],
      }),
    });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    fireEvent.change(await within(pane).findByLabelText("Reply"), {
      target: { value: "a < b\nline two" },
    });
    fireEvent.click(within(pane).getByRole("button", { name: "Send reply" }));
    await waitFor(() =>
      expect(api.replyToInboxThread).toHaveBeenCalledWith(1, {
        body: "<p>a &lt; b<br>line two</p>",
        lastSeenMessageId: 11,
      }),
    );
    await waitFor(() =>
      expect(within(pane).getByLabelText("Reply")).toHaveValue(""),
    );
  });

  it("on 409 warns, keeps the draft, reloads, and resends with the new id", async () => {
    api.replyToInboxThread
      .mockRejectedValueOnce({ response: { status: 409 }, message: "conflict" })
      .mockResolvedValueOnce({ data: detail({ latestMessageId: 13 }) });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    fireEvent.change(await within(pane).findByLabelText("Reply"), {
      target: { value: "my draft" },
    });
    api.getInboxThread.mockResolvedValue({
      data: detail({
        latestMessageId: 12,
        messages: [message(), message({ messageId: 12, bodyText: "new one" })],
      }),
    });
    fireEvent.click(within(pane).getByRole("button", { name: "Send reply" }));
    expect(
      await within(pane).findByText(/Not sent: this thread has new messages/),
    ).toBeInTheDocument();
    expect(within(pane).getByLabelText("Reply")).toHaveValue("my draft");
    expect(errorSpy).not.toHaveBeenCalled();
    await within(pane).findByText("new one");
    fireEvent.click(within(pane).getByRole("button", { name: "Send reply" }));
    await waitFor(() =>
      expect(api.replyToInboxThread).toHaveBeenLastCalledWith(1, {
        body: "<p>my draft</p>",
        lastSeenMessageId: 12,
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByText(/Not sent: this thread has new messages/),
      ).toBeNull(),
    );
  });

  it("toasts other send failures", async () => {
    api.replyToInboxThread.mockRejectedValue({
      response: { status: 500 },
      message: "boom",
    });
    renderAt();
    await screen.findByRole("button", { name: /Open thread Question/ });
    open("Question about meeting cadence");
    const pane = await thread();
    fireEvent.change(await within(pane).findByLabelText("Reply"), {
      target: { value: "hi" },
    });
    fireEvent.click(within(pane).getByRole("button", { name: "Send reply" }));
    await waitFor(() => expect(errorSpy).toHaveBeenCalledWith("boom"));
  });
});
