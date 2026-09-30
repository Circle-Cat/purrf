import { describe, it, expect } from "vitest";
import {
  render,
  screen,
  fireEvent,
  within,
  waitFor,
} from "@testing-library/react";
import ApplicationEmailsPrototype from "@/pages/ApplicationEmailsPrototype";

const switchTo = (id) =>
  fireEvent.change(screen.getByLabelText("Application"), {
    target: { value: String(id) },
  });

const thread = (subject) =>
  within(screen.getByRole("listitem", { name: `Thread ${subject}` }));

const message = (id) => screen.getByRole("listitem", { name: `Message ${id}` });

const dialog = () => within(screen.getByRole("dialog"));

const write = (html) => {
  const editor = dialog().getByRole("textbox", { name: "Message" });
  editor.innerHTML = html;
  fireEvent.input(editor);
};

const send = async () => {
  fireEvent.click(dialog().getByRole("button", { name: "Send" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
};

describe("ApplicationEmailsPrototype", () => {
  it("lists the five changes in a collapsible panel", () => {
    render(<ApplicationEmailsPrototype />);
    const toggle = screen.getByRole("button", {
      name: "What changed vs today",
    });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("From line in the composer.")).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("From line in the composer.")).toBeNull();
  });

  it("1. shows a read-only From alias set by the posting type", () => {
    render(<ApplicationEmailsPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Send email" }));
    expect(dialog().getByLabelText("From")).toHaveTextContent(
      "recruiting@circlecat.org",
    );
    expect(dialog().getByLabelText("From").tagName).toBe("P");
    fireEvent.click(dialog().getByRole("button", { name: "Cancel" }));

    switchTo(41);
    fireEvent.click(
      thread("Your mentee application").getByRole("button", { name: "Reply" }),
    );
    expect(dialog().getByLabelText("From")).toHaveTextContent(
      "mentorship@circlecat.org",
    );
  });

  it("2. starts a new email with an empty Cc; a reply prefills the thread's Cc", () => {
    render(<ApplicationEmailsPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Send email" }));
    expect(dialog().getByLabelText("To")).toHaveValue(
      "arjun.mehta@example.com",
    );
    expect(dialog().getByLabelText("Cc")).toHaveValue("");
    fireEvent.click(dialog().getByRole("button", { name: "Cancel" }));

    fireEvent.click(
      thread("Circle Cat Program - Interview Availability").getByRole(
        "button",
        { name: "Reply" },
      ),
    );
    expect(dialog().getByLabelText("Cc")).toHaveValue(
      "priya.shah@circlecat.org",
    );
    expect(dialog().getByLabelText("Subject")).toHaveValue(
      "Re: Circle Cat Program - Interview Availability",
    );
    fireEvent.click(dialog().getByRole("button", { name: "Cancel" }));

    // Neither the candidate nor our own aliases are carried over.
    switchTo(41);
    fireEvent.click(
      thread("Your mentee application").getByRole("button", { name: "Reply" }),
    );
    expect(dialog().getByLabelText("Cc")).toHaveValue(
      "mentor.team@circlecat.org",
    );
  });

  it("3. names From and To on each message, showing the alias change", () => {
    render(<ApplicationEmailsPrototype />);
    switchTo(41);
    expect(message("4101-1")).toHaveTextContent("Fromrecruiting@circlecat.org");
    expect(message("4101-1")).toHaveTextContent("Todaniel.okafor@example.com");
    expect(message("4101-2")).toHaveTextContent("Frommentorship@circlecat.org");
    expect(message("4101-3")).toHaveTextContent(
      "Fromdaniel.okafor@example.com",
    );
    expect(message("4101-3")).toHaveTextContent("Tomentorship@circlecat.org");
  });

  it("4. tags auto-replies and bounces, and clears the bounce banner after a new send", async () => {
    render(<ApplicationEmailsPrototype />);
    const bounced = "Your Circle Cat Technical Interview is Scheduled";
    expect(message("8802-2")).toHaveTextContent("Delivery failed");
    expect(thread(bounced).getByRole("alert")).toHaveTextContent(
      "Delivery failed: your email to arjun.m@oldmail.example.org was not delivered",
    );
    expect(
      thread("Circle Cat Program - Interview Availability").queryByRole(
        "alert",
      ),
    ).toBeNull();

    fireEvent.click(thread(bounced).getByRole("button", { name: "Reply" }));
    write("<p>Resending to your current address.</p>");
    await send();
    expect(thread(bounced).queryByRole("alert")).toBeNull();

    switchTo(104);
    expect(message("10401-3")).toHaveTextContent("Auto-reply");
    expect(message("10401-3").className).toMatch(/opacity-75/);
    expect(message("10401-2").className).not.toMatch(/opacity-75/);
    // An auto-reply is not someone writing in.
    expect(
      thread("Scheduling your first interview").queryByText("Needs reply"),
    ).toBeNull();
  });

  it("5. marks the thread and tab Needs reply until we reply", async () => {
    render(<ApplicationEmailsPrototype />);
    expect(screen.queryByLabelText("Needs reply")).toBeNull();

    switchTo(41);
    expect(
      thread("Your mentee application").getByText("Needs reply"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Needs reply")).toBeInTheDocument();

    fireEvent.click(
      thread("Your mentee application").getByRole("button", { name: "Reply" }),
    );
    write("<p>Here is a direct link to the course.</p>");
    await send();

    expect(
      thread("Your mentee application").queryByText("Needs reply"),
    ).toBeNull();
    expect(screen.queryByLabelText("Needs reply")).toBeNull();
    const sent = screen.getByText("Here is a direct link to the course.");
    expect(sent.closest("li")).toHaveTextContent(
      "Frommentorship@circlecat.org",
    );
  });

  it("keeps the real composer: templates highlight markers and warn before sending", () => {
    render(<ApplicationEmailsPrototype />);
    fireEvent.click(screen.getByRole("button", { name: "Send email" }));
    fireEvent.change(dialog().getByLabelText("Template"), {
      target: { value: "cultural_interview_scheduled" },
    });
    expect(dialog().getByLabelText("Subject")).toHaveValue(
      "Your Circle Cat Behavioral Interview is Scheduled",
    );
    expect(
      dialog().getByText("Applied: Behavioral interview scheduled"),
    ).toBeInTheDocument();
    const editor = dialog().getByRole("textbox", { name: "Message" });
    expect(editor).toHaveTextContent("Dear Arjun Mehta,");
    expect(editor.querySelector("mark")).toHaveTextContent(
      "[INTERVIEW DATE/TIME]",
    );

    fireEvent.click(dialog().getByRole("button", { name: "Send" }));
    expect(screen.getByText("Unfilled placeholders")).toBeInTheDocument();
  });
});
