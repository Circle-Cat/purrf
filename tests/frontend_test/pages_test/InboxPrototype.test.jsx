import { afterEach, describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import InboxPrototype from "@/pages/InboxPrototype";

const serviceChip = (name) =>
  within(screen.getByRole("group", { name: "Services" })).getByRole("button", {
    name: new RegExp(`^${name}`),
  });

const renderAt = (hash) => {
  window.history.replaceState(null, "", hash);
  render(<InboxPrototype />);
};

const send = (text) => {
  fireEvent.change(within(thread()).getByLabelText("Reply"), {
    target: { value: text },
  });
  fireEvent.click(within(thread()).getByRole("button", { name: "Send reply" }));
};

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
  it("mixes every service in one list, with a sidebar badge and service filter", () => {
    render(<InboxPrototype />);
    expect(screen.getByRole("heading", { name: "Inbox" })).toBeInTheDocument();
    for (const alias of [
      "mentorship@circlecat.org",
      "recruiting@circlecat.org",
      "inquiries@circlecat.org",
    ]) {
      expect(screen.getByText(alias)).toBeInTheDocument();
    }
    // One thread from each service in the same list.
    expect(listed("Question about meeting cadence")).not.toBeNull();
    expect(listed("Follow-up on my interview")).not.toBeNull();
    expect(listed("Donation receipt request")).not.toBeNull();
    expect(rowOf("Follow-up on my interview")).toHaveTextContent("Recruiting");

    // 5 needing a reply in each service.
    expect(screen.getByLabelText("Sidebar Inbox entry")).toHaveTextContent(
      "Inbox15",
    );
    expect(screen.getByText("Needs reply: 15")).toBeInTheDocument();
    expect(serviceChip("Recruiting")).toHaveTextContent("Recruiting5");

    fireEvent.click(serviceChip("Recruiting"));
    expect(listed("Question about meeting cadence")).toBeNull();
    expect(listed("Follow-up on my interview")).not.toBeNull();
    expect(window.location.hash).toBe("#inbox/recruiting");

    fireEvent.click(serviceChip("All"));
    expect(listed("Question about meeting cadence")).not.toBeNull();
  });

  it("shows only the services the viewer holds a permission for", () => {
    render(<InboxPrototype />);
    fireEvent.click(screen.getByLabelText("recruiting.application.advance"));
    fireEvent.click(screen.getByLabelText("inquiries.manage"));
    expect(listed("Follow-up on my interview")).toBeNull();
    expect(listed("Donation receipt request")).toBeNull();
    expect(screen.queryByText("recruiting@circlecat.org")).toBeNull();
    expect(screen.getByLabelText("Sidebar Inbox entry")).toHaveTextContent(
      "Inbox5",
    );
    expect(
      within(screen.getByRole("group", { name: "Services" })).queryByRole(
        "button",
        { name: /^Recruiting/ },
      ),
    ).toBeNull();

    fireEvent.click(screen.getByLabelText("mentorship.admin.write"));
    expect(screen.queryByLabelText("Sidebar Inbox entry")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Inbox" })).toBeNull();
  });

  it("lists every non-archived thread by default, and chips narrow with AND", () => {
    renderAt("#inbox/mentorship");
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
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (3)");
    const rows = () =>
      screen.getAllByRole("button", { name: /^Open thread / }).length;
    expect(rows()).toBe(8);

    toggle("Needs reply");
    expect(rows()).toBe(5);
    expect(listed("Requesting a different mentee")).not.toBeNull();

    toggle("Unassigned");
    expect(rows()).toBe(2);
    expect(listed("Requesting a different mentee")).toBeNull();
    expect(listed("Thank you for the workshop")).toBeNull();
    expect(listed("Can I still join the Fall round?")).not.toBeNull();

    toggle("Needs reply");
    expect(rows()).toBe(3);
    expect(listed("Thank you for the workshop")).not.toBeNull();
  });

  it("puts needs-reply threads first by latest inbound, then the rest by activity", () => {
    renderAt("#inbox/mentorship");
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
    renderAt("#inbox/mentorship");
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
    // IDs match exactly, never as a substring.
    search("155");
    expect(titles()).toEqual([]);
    search("#155");
    expect(titles()).toEqual([]);
    // A digits-only query is an ID, not text: "2026" appears in a subject
    // ("Fall 2026 pairing details") but matches nothing.
    search("2026");
    expect(titles()).toEqual([]);

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
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (3)");

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

  it("finds a sender with no matching user by the assigned person's name and #id", () => {
    renderAt("#inbox/mentorship");
    const search = (value) =>
      fireEvent.change(screen.getByLabelText("Search threads"), {
        target: { value },
      });

    search("Elena");
    expect(listed("Interested in becoming a mentor")).toBeNull();

    search("");
    openThread("Interested in becoming a mentor");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Search people"), {
      target: { value: "Elena" },
    });
    fireEvent.click(dialog.getByRole("button", { name: /Elena Petrova/ }));
    fireEvent.click(dialog.getByRole("button", { name: "Assign" }));

    search("elena petrova");
    expect(listed("Interested in becoming a mentor")).not.toBeNull();
    search("#1715");
    expect(listed("Interested in becoming a mentor")).not.toBeNull();
    search("jordan.blake");
    expect(listed("Interested in becoming a mentor")).not.toBeNull();
  });

  it("shows the application chip and the alias change on a mentee thread", () => {
    renderAt("#inbox/mentorship");
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
    renderAt("#inbox/mentorship");
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
    expect(chip("Needs reply")).toHaveTextContent("Needs reply (4)");
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
    renderAt("#inbox/inquiries");
    openThread("Sponsorship follow-up");
    expect(within(thread()).getByRole("alert")).toHaveTextContent(
      "Delivery failed: your email to info@oldcompany.example was not delivered",
    );
  });

  it("assigns a mentorship thread matched by alternative email to a round", () => {
    renderAt("#inbox/mentorship");
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

  it("keeps a sender with no matching user out of Unassigned, but assignable by hand", () => {
    renderAt("#inbox/mentorship");
    const row = rowOf("Interested in becoming a mentor");
    expect(row).toHaveTextContent("No matching user");
    expect(row).not.toHaveTextContent("Unassigned");
    expect(row).toHaveTextContent("Needs reply");

    expect(chip("Unassigned")).toHaveTextContent("Unassigned (3)");
    toggle("Unassigned");
    expect(listed("Interested in becoming a mentor")).toBeNull();
    toggle("Unassigned");

    openThread("Interested in becoming a mentor");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Search people"), {
      target: { value: "1715" },
    });
    fireEvent.click(dialog.getByRole("button", { name: /Elena Petrova/ }));
    fireEvent.click(dialog.getByRole("button", { name: "Assign" }));

    expect(rowOf("Interested in becoming a mentor")).toHaveTextContent(
      "Fall 2026 round",
    );
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (3)");
  });

  it("makes a sender with no matching user pick a person first", () => {
    renderAt("#inbox/mentorship");
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
    renderAt("#inbox/recruiting");

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

  it("moves an inquiry to another service as unassigned, replying from its alias", () => {
    renderAt("#inbox/inquiries");
    openThread("Is there a mentorship program for engineers?");
    fireEvent.change(within(thread()).getByLabelText("Move to"), {
      target: { value: "mentorship" },
    });
    fireEvent.click(within(thread()).getByRole("button", { name: "Move" }));
    expect(listed("Is there a mentorship program for engineers?")).toBeNull();

    fireEvent.click(serviceChip("Mentorship"));
    toggle("Unassigned");
    expect(screen.getByText("Moved from Inquiries")).toBeInTheDocument();
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
    send("Yes — you can register for the next round.");
    const sent = within(thread())
      .getByText("Yes — you can register for the next round.")
      .closest("li");
    expect(sent).toHaveTextContent("Frommentorship@circlecat.org");
  });

  it("moves in any direction, clearing assignment and archive", () => {
    renderAt("#inbox/mentorship");
    openThread("Requesting a different mentee");
    fireEvent.click(within(thread()).getByRole("button", { name: "Archive" }));
    const options = within(within(thread()).getByLabelText("Move to"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(options).toEqual(["Move to…", "Recruiting", "Inquiries"]);
    fireEvent.change(within(thread()).getByLabelText("Move to"), {
      target: { value: "inquiries" },
    });
    fireEvent.click(within(thread()).getByRole("button", { name: "Move" }));

    fireEvent.click(serviceChip("Inquiries"));
    const row = rowOf("Requesting a different mentee");
    expect(row).toHaveTextContent("Moved from Mentorship");
    expect(row).not.toHaveTextContent("Fall 2026 round");
    expect(row).not.toHaveTextContent("Archived");
    expect(row).toHaveTextContent("Needs reply");
  });

  it("drops a moved thread from view when the viewer can't see its new service", () => {
    render(<InboxPrototype />);
    fireEvent.click(screen.getByLabelText("recruiting.application.advance"));
    openThread("Question about meeting cadence");
    fireEvent.change(within(thread()).getByLabelText("Move to"), {
      target: { value: "recruiting" },
    });
    fireEvent.click(within(thread()).getByRole("button", { name: "Move" }));
    expect(listed("Question about meeting cadence")).toBeNull();
    expect(screen.queryByRole("region", { name: "Thread" })).toBeNull();
  });

  it("gives a tracked application thread neither Assign nor Move", () => {
    renderAt("#inbox/mentorship");
    openThread("Your mentee application");
    expect(within(thread()).queryByLabelText("Move to")).toBeNull();
    expect(
      within(thread()).queryByRole("button", { name: "Assign" }),
    ).toBeNull();
    expect(
      within(thread()).queryByRole("button", { name: "Reassign" }),
    ).toBeNull();
  });

  it("lets an assigned recruiting thread be reassigned", () => {
    renderAt("#inbox/recruiting");
    openThread("Take-home assignment question");
    expect(
      within(thread()).getByRole("button", { name: "Reassign" }),
    ).toBeInTheDocument();
  });

  it("never assigns an inquiry and never counts it as Unassigned", () => {
    renderAt("#inbox/inquiries");
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (0)");
    expect(rowOf("Volunteer opportunities")).not.toHaveTextContent(
      "Unassigned",
    );
    openThread("Volunteer opportunities");
    expect(
      within(thread()).queryByRole("button", { name: "Assign" }),
    ).toBeNull();
    expect(within(thread()).getByLabelText("Move to")).toBeInTheDocument();
  });

  it("removes an assignment, sending the thread back to Unassigned", () => {
    renderAt("#inbox/mentorship");
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (3)");
    openThread("Requesting a different mentee");
    fireEvent.click(within(thread()).getByRole("button", { name: "Reassign" }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Remove assignment",
      }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    const row = rowOf("Requesting a different mentee");
    expect(row).toHaveTextContent("Unassigned");
    expect(row).not.toHaveTextContent("Fall 2026 round");
    expect(chip("Unassigned")).toHaveTextContent("Unassigned (4)");
    expect(
      within(thread()).getByRole("button", { name: "Assign" }),
    ).toBeInTheDocument();
  });

  it("offers no Remove assignment on an unassigned thread", () => {
    renderAt("#inbox/mentorship");
    openThread("Question about meeting cadence");
    fireEvent.click(within(thread()).getByRole("button", { name: "Assign" }));
    expect(
      within(screen.getByRole("dialog")).queryByRole("button", {
        name: "Remove assignment",
      }),
    ).toBeNull();
  });

  it("refuses a send once when a message arrived after opening, keeping the draft", () => {
    renderAt("#inbox/mentorship");
    openThread("Question about meeting cadence");
    fireEvent.click(
      within(thread()).getByRole("button", {
        name: "Dev: simulate colleague reply",
      }),
    );
    send("Every three weeks is fine.");
    expect(within(thread()).getByRole("status")).toHaveTextContent(
      "Not sent: this thread has new messages",
    );
    expect(within(thread()).getByLabelText("Reply")).toHaveValue(
      "Every three weeks is fine.",
    );
    expect(
      within(thread()).queryByText("Every three weeks is fine.", {
        selector: "p",
      }),
    ).toBeNull();

    fireEvent.click(
      within(thread()).getByRole("button", { name: "Send reply" }),
    );
    expect(
      within(thread()).getByText("Every three weeks is fine.", {
        selector: "p",
      }),
    ).toBeInTheDocument();
    expect(within(thread()).queryByRole("status")).toBeNull();

    // Our own send is not "new since opening".
    send("One more thing.");
    expect(
      within(thread()).getByText("One more thing.", { selector: "p" }),
    ).toBeInTheDocument();
  });

  it("lists inbound attachments and downloads on click", () => {
    renderAt("#inbox/recruiting");
    openThread("Resume for any open role");
    const files = within(thread()).getByRole("list", { name: "Attachments" });
    expect(files).toHaveTextContent("Kevin_Zhou_Resume.pdf182 KB");
    fireEvent.click(
      within(files).getByRole("button", { name: /Portfolio_Links\.docx/ }),
    );
    expect(
      within(thread()).getByText(/Would download Portfolio_Links\.docx/),
    ).toBeInTheDocument();
  });
});
