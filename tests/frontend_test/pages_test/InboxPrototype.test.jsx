import { afterEach, describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import InboxPrototype from "@/pages/InboxPrototype";

const inboxButton = (name) =>
  within(screen.getByRole("navigation", { name: "Inboxes" })).getByRole(
    "button",
    { name: new RegExp(`^${name}`) },
  );

const openThread = (subject) =>
  fireEvent.click(
    screen.getByRole("button", { name: `Open thread ${subject}` }),
  );

const thread = () => screen.getByRole("region", { name: "Thread" });

const listed = (subject) =>
  screen.queryByRole("button", { name: `Open thread ${subject}` });

const chip = (name) =>
  within(screen.getByRole("group", { name: "Filters" })).getByRole("button", {
    name: new RegExp(`^${name} \\(`),
  });

const toggle = (name) => fireEvent.click(chip(name));

const rowOf = (subject) => listed(subject).closest("li");

afterEach(() => {
  window.history.replaceState(null, "", window.location.pathname);
});

describe("InboxPrototype", () => {
  it("renders each inbox with its alias and needs-reply count", () => {
    render(<InboxPrototype />);
    expect(
      screen.getByRole("heading", { name: "Mentorship inbox" }),
    ).toBeInTheDocument();
    expect(screen.getByText("mentorship@circlecat.org")).toBeInTheDocument();
    expect(screen.getByText("Needs reply: 5")).toBeInTheDocument();
    expect(screen.getByText("Wang Xiao")).toBeInTheDocument();
    expect(screen.getByText("jordan.blake@example.net")).toBeInTheDocument();

    fireEvent.click(inboxButton("Recruiting"));
    expect(
      screen.getByRole("heading", { name: "Recruiting inbox" }),
    ).toBeInTheDocument();
    expect(screen.getByText("recruiting@circlecat.org")).toBeInTheDocument();

    fireEvent.click(inboxButton("Inquiries"));
    expect(
      screen.getByText("Draft — scope under discussion"),
    ).toBeInTheDocument();
    expect(screen.getByText("inquiries@circlecat.org")).toBeInTheDocument();
  });

  it("lists every non-archived thread by default, and chips narrow with AND", () => {
    render(<InboxPrototype />);
    // Assigned and already replied: in neither filter, still in the list.
    expect(listed("Fall 2026 pairing details")).not.toBeNull();
    expect(listed("Midpoint check-in")).not.toBeNull();
    expect(listed("Partnership opportunity for your mentees")).toBeNull();

    expect(rowOf("Question about meeting cadence")).toHaveTextContent(
      "Needs reply",
    );
    expect(rowOf("Question about meeting cadence")).toHaveTextContent(
      "Unassigned",
    );
    expect(rowOf("Thank you for the workshop")).not.toHaveTextContent(
      "Needs reply",
    );

    expect(chip("Needs reply")).toHaveTextContent("Needs reply (5)");
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (4)");
    const rows = () =>
      screen.getAllByRole("button", { name: /^Open thread / }).length;
    expect(rows()).toBe(8);

    toggle("Needs reply");
    expect(rows()).toBe(5);
    expect(listed("Requesting a different mentee")).not.toBeNull();

    toggle("Unassigned");
    expect(rows()).toBe(3);
    expect(listed("Requesting a different mentee")).toBeNull();
    expect(listed("Thank you for the workshop")).toBeNull();
    expect(listed("Interested in becoming a mentor")).not.toBeNull();

    toggle("Needs reply");
    expect(rows()).toBe(4);
    expect(listed("Thank you for the workshop")).not.toBeNull();
  });

  it("puts needs-reply threads first by latest inbound, then the rest by activity", () => {
    render(<InboxPrototype />);
    const order = () =>
      screen
        .getAllByRole("button", { name: /^Open thread / })
        .map((b) => b.getAttribute("aria-label").replace("Open thread ", ""));
    expect(order()).toEqual([
      "Question about meeting cadence",
      "Requesting a different mentee",
      "Can I still join the Fall round?",
      "Your mentee application",
      "Interested in becoming a mentor",
      "Thank you for the workshop",
      "Midpoint check-in",
      "Fall 2026 pairing details",
    ]);

    // Replying makes this the newest activity, but it no longer needs a
    // reply, so the older needs-reply threads stay above it.
    openThread("Question about meeting cadence");
    fireEvent.change(within(thread()).getByLabelText("Reply"), {
      target: { value: "Every three weeks is fine." },
    });
    fireEvent.click(
      within(thread()).getByRole("button", { name: "Send reply" }),
    );
    expect(order()).toEqual([
      "Requesting a different mentee",
      "Can I still join the Fall round?",
      "Your mentee application",
      "Interested in becoming a mentor",
      "Question about meeting cadence",
      "Thank you for the workshop",
      "Midpoint check-in",
      "Fall 2026 pairing details",
    ]);
  });

  it("searches by name, user ID, email and subject, combined with chips", () => {
    render(<InboxPrototype />);
    const search = (value) =>
      fireEvent.change(screen.getByLabelText("Search threads"), {
        target: { value },
      });
    const titles = () =>
      screen
        .queryAllByRole("button", { name: /^Open thread / })
        .map((b) => b.getAttribute("aria-label").replace("Open thread ", ""));

    search("wang XIAO");
    expect(titles()).toEqual(["Question about meeting cadence"]);

    search("#1555");
    expect(titles()).toEqual(["Requesting a different mentee"]);
    search("1555");
    expect(titles()).toEqual(["Requesting a different mentee"]);

    search("jordan.blake@");
    expect(titles()).toEqual(["Interested in becoming a mentor"]);
    search("mchen.personal");
    expect(titles()).toEqual(["Can I still join the Fall round?"]);

    search("cadence");
    expect(titles()).toEqual(["Question about meeting cadence"]);

    search("fall");
    expect(titles()).toEqual([
      "Can I still join the Fall round?",
      "Fall 2026 pairing details",
    ]);
    toggle("Needs reply");
    expect(titles()).toEqual(["Can I still join the Fall round?"]);
    // Counts ignore the search.
    expect(chip("Needs reply")).toHaveTextContent("Needs reply (5)");
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (4)");

    search("pairing");
    expect(titles()).toEqual([]);
    expect(screen.getByText(/No threads match "pairing"/)).toBeInTheDocument();

    search("partnerco");
    expect(titles()).toEqual([]);
    toggle("Needs reply");
    expect(titles()).toEqual([]);
    fireEvent.click(screen.getByLabelText("Show archived"));
    expect(titles()).toEqual(["Partnership opportunity for your mentees"]);
  });

  it("shows the application chip and the alias change on a mentee thread", () => {
    render(<InboxPrototype />);
    expect(
      screen.getByText("Mentee 2026 · application #41"),
    ).toBeInTheDocument();
    openThread("Your mentee application");
    const t = within(thread());
    expect(t.getAllByText("recruiting@circlecat.org").length).toBeGreaterThan(
      0,
    );
    expect(
      t.getByText("mentorship@circlecat.org", { selector: "span" }),
    ).toBeInTheDocument();
    expect(
      t.getByRole("button", { name: "View application on Applications Board" }),
    ).toBeInTheDocument();
    expect(t.queryByRole("button", { name: "Assign" })).toBeNull();
  });

  it("replying takes a thread out of Needs reply; archive hides it until a new reply", () => {
    render(<InboxPrototype />);
    toggle("Needs reply");
    openThread("Question about meeting cadence");
    fireEvent.change(within(thread()).getByLabelText("Reply"), {
      target: { value: "Every three weeks is fine." },
    });
    fireEvent.click(
      within(thread()).getByRole("button", { name: "Send reply" }),
    );
    expect(listed("Question about meeting cadence")).toBeNull();
    expect(
      within(thread()).getByText("Every three weeks is fine."),
    ).toBeInTheDocument();
    expect(screen.getByText("Needs reply: 4")).toBeInTheDocument();
    toggle("Needs reply");
    expect(listed("Question about meeting cadence")).not.toBeNull();

    openThread("Interested in becoming a mentor");
    fireEvent.click(within(thread()).getByRole("button", { name: "Archive" }));
    expect(listed("Interested in becoming a mentor")).toBeNull();

    fireEvent.click(screen.getByLabelText("Show archived"));
    expect(listed("Interested in becoming a mentor")).not.toBeNull();
    fireEvent.click(screen.getByLabelText("Show archived"));

    fireEvent.click(
      within(thread()).getByRole("button", { name: "Dev: simulate new reply" }),
    );
    expect(listed("Interested in becoming a mentor")).not.toBeNull();
  });

  it("shows a bounce banner on a tracked thread", () => {
    window.history.replaceState(null, "", "#inbox/inquiries");
    render(<InboxPrototype />);
    openThread("Sponsorship follow-up");
    expect(within(thread()).getByRole("alert")).toHaveTextContent(
      "Delivery failed: your email to info@oldcompany.example was not delivered",
    );
  });

  it("assigns a mentorship thread matched by alternative email to a round", () => {
    render(<InboxPrototype />);
    openThread("Can I still join the Fall round?");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    const dialog = within(screen.getByRole("dialog"));
    expect(
      dialog.getByText("Matched by alternative email"),
    ).toBeInTheDocument();
    const round = dialog.getByLabelText("Round");
    expect(round).toHaveValue("Fall 2026");
    expect(
      dialog.getByRole("option", {
        name: "Fall 2026 (current) — Not registered",
      }),
    ).toBeInTheDocument();
    fireEvent.click(dialog.getByRole("button", { name: "Assign" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(listed("Can I still join the Fall round?")).not.toBeNull();
    expect(rowOf("Can I still join the Fall round?")).not.toHaveTextContent(
      "Unassigned",
    );
    toggle("Unassigned");
    expect(listed("Can I still join the Fall round?")).toBeNull();
  });

  it("makes an unknown sender pick a person first", () => {
    render(<InboxPrototype />);
    openThread("Interested in becoming a mentor");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByRole("button", { name: "Assign" })).toBeDisabled();
    fireEvent.change(dialog.getByLabelText("Search people"), {
      target: { value: "Elena" },
    });
    fireEvent.click(dialog.getByRole("button", { name: /Elena Petrova/ }));
    expect(dialog.getByLabelText("Selected person")).toHaveTextContent(
      "Elena Petrova · #1715",
    );
    expect(dialog.getByRole("button", { name: "Assign" })).toBeEnabled();
  });

  it("picks the application a recruiting thread attaches to", () => {
    window.history.replaceState(null, "", "#inbox/recruiting");
    render(<InboxPrototype />);

    openThread("Follow-up on my interview");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    let dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Job"), {
      target: { value: "backend" },
    });
    expect(
      dialog.getByText("Attaches to application #88 (In progress)"),
    ).toBeInTheDocument();
    fireEvent.click(dialog.getByRole("button", { name: "Assign" }));
    expect(
      screen.getAllByText("Backend Engineer · application #88").length,
    ).toBeGreaterThan(0);

    openThread("Can I reapply?");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Job"), {
      target: { value: "analyst" },
    });
    expect(
      dialog.getByText("Attaches to most recent application #57 (Rejected)"),
    ).toBeInTheDocument();
    fireEvent.click(dialog.getByRole("button", { name: "Cancel" }));

    openThread("Do you offer internships?");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText(/can't be assigned/)).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Assign" })).toBeDisabled();
  });

  it("moves an inquiry to another inbox as unassigned, replying from its alias", () => {
    window.history.replaceState(null, "", "#inbox/inquiries");
    render(<InboxPrototype />);
    openThread("Is there a mentorship program for engineers?");
    fireEvent.change(within(thread()).getByLabelText("Move to"), {
      target: { value: "mentorship" },
    });
    fireEvent.click(within(thread()).getByRole("button", { name: "Move" }));
    expect(listed("Is there a mentorship program for engineers?")).toBeNull();

    fireEvent.click(inboxButton("Mentorship"));
    toggle("Unassigned");
    expect(screen.getByText("Moved from Inquiries")).toBeInTheDocument();
    openThread("Is there a mentorship program for engineers?");
    expect(
      within(thread()).getByText("mentorship@circlecat.org", {
        selector: "span.font-medium",
      }),
    ).toBeInTheDocument();
    expect(
      within(thread()).getByText(
        "Moved from Inquiries — replies now sent from mentorship@circlecat.org",
      ),
    ).toBeInTheDocument();
    fireEvent.change(within(thread()).getByLabelText("Reply"), {
      target: { value: "Yes — you can register for the next round." },
    });
    fireEvent.click(
      within(thread()).getByRole("button", { name: "Send reply" }),
    );
    const sent = within(thread())
      .getByText("Yes — you can register for the next round.")
      .closest("li");
    expect(sent).toHaveTextContent("Frommentorship@circlecat.org");
  });
});
