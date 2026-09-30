import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import EmailTemplatesPrototype from "@/pages/EmailTemplatesPrototype";

const rows = () => screen.queryAllByRole("button", { name: /^Open template / });

const open = (name) =>
  fireEvent.click(
    screen.getByRole("button", { name: `Open template ${name}` }),
  );

const preview = () =>
  within(screen.getByRole("region", { name: "Template preview" }));

describe("EmailTemplatesPrototype", () => {
  it("lists every template plus the planned ones, grouped by service", () => {
    render(<EmailTemplatesPrototype />);
    expect(screen.getByText("28 templates")).toBeInTheDocument();
    expect(screen.getByText("2 planned")).toBeInTheDocument();
    expect(rows()).toHaveLength(30);
    expect(
      screen.getByRole("region", { name: "Recruiting templates" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Users templates" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Visible to", { exact: false })).toHaveTextContent(
      "Visible to ops.alert",
    );
    expect(
      screen.getByText(/Not listed: Auth0 sign-in codes/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: /\(planned\)$/ }),
    ).toHaveLength(2);
  });

  it("filters by send mode and service", () => {
    render(<EmailTemplatesPrototype />);
    fireEvent.change(screen.getByLabelText("Send mode"), {
      target: { value: "manual" },
    });
    expect(rows()).toHaveLength(8);

    fireEvent.change(screen.getByLabelText("Send mode"), {
      target: { value: "automatic" },
    });
    fireEvent.change(screen.getByLabelText("Service"), {
      target: { value: "users" },
    });
    expect(rows()).toHaveLength(3);
  });

  it("previews a manual template with sample values, raw placeholders and highlighted markers", () => {
    render(<EmailTemplatesPrototype />);
    open("Behavioral interview scheduled");
    const p = preview();
    const body = p.getByLabelText("Preview body");
    expect(body).toHaveTextContent("Dear Jordan Rivera,");
    expect(body).toHaveTextContent("Best,Morgan Lee");
    const marker = body.querySelector("mark.marker");
    expect(marker).toHaveTextContent("[INTERVIEW DATE/TIME]");
    expect(
      p.getByText("recruiting@circlecat.org", { selector: "code" }),
    ).toBeInTheDocument();

    fireEvent.click(p.getByLabelText("Show placeholders"));
    expect(body).toHaveTextContent("Dear {{candidate_name}},");
    expect(body).not.toHaveTextContent("Jordan Rivera");
    const list = p.getByRole("list", { name: "Placeholders" });
    expect(list).toHaveTextContent("{{candidate_name}}");
    expect(list).toHaveTextContent("{{sender_name}}");
    expect(list).toHaveTextContent("[INTERVIEW DATE/TIME]");
  });

  it("previews an automatic template with trigger, recipients and variants", () => {
    render(<EmailTemplatesPrototype />);
    open("Block request decided");
    const p = preview();
    expect(
      p.getByText("When the reviewer approves or rejects a block request"),
    ).toBeInTheDocument();
    expect(p.getByText("Whoever raised the request")).toBeInTheDocument();
    expect(
      p.getByText("notifications@circlecat.org", { selector: "code" }),
    ).toBeInTheDocument();
    expect(p.getByText("alias TBD")).toBeInTheDocument();
    expect(p.getByLabelText("Preview subject")).toHaveTextContent(
      "Your block request was approved",
    );
    fireEvent.click(p.getByRole("button", { name: "Rejected" }));
    expect(p.getByLabelText("Preview subject")).toHaveTextContent(
      "Your block request was rejected",
    );
    expect(p.queryByLabelText("Show placeholders")).toBeNull();

    open("Round advanced");
    expect(preview().getByLabelText("unverified")).toBeInTheDocument();
  });

  it("shows a planned entry without a preview", () => {
    render(<EmailTemplatesPrototype />);
    fireEvent.click(screen.getAllByRole("button", { name: /\(planned\)$/ })[0]);
    expect(preview().getByText(/doesn't exist yet/)).toBeInTheDocument();
    expect(preview().queryByLabelText("Preview body")).toBeNull();
  });

  it("searches name, key and subject", () => {
    render(<EmailTemplatesPrototype />);
    const search = (value) =>
      fireEvent.change(screen.getByLabelText("Search templates"), {
        target: { value },
      });

    search("rejection");
    expect(rows().map((r) => r.getAttribute("aria-label"))).toEqual([
      "Open template Rejection",
    ]);

    search("user.block_request");
    expect(rows()).toHaveLength(3);

    search("Welcome to Circle Cat Mentorship");
    expect(rows().map((r) => r.getAttribute("aria-label"))).toEqual([
      "Open template Mentor admitted",
    ]);

    search("zzz-nothing");
    expect(rows()).toHaveLength(0);
    expect(screen.getByText("No templates match.")).toBeInTheDocument();
  });
});
