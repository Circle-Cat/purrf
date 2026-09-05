import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PipelineConfigEditor from "@/pages/Recruiting/postings/PipelineConfigEditor";

const POOL = [{ userId: 7, name: "Ann", email: "ann@x.com" }];
const OWNERS = [
  { userId: 42, name: "Bo", email: "bo@x.com" },
  { userId: 43, name: "Cy", email: "cy@x.com" },
];

const renderEditor = (value, onChange) =>
  render(
    <PipelineConfigEditor
      value={value}
      onChange={onChange}
      interviewPool={POOL}
      jobOwners={OWNERS}
    />,
  );

describe("PipelineConfigEditor", () => {
  it("adds a stage in canonical order when its checkbox is ticked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ stages: [] }, onChange);
    await user.click(screen.getByRole("checkbox", { name: "Behavioral" }));
    expect(onChange).toHaveBeenCalledWith({
      stages: [{ stage: "behavioral", rounds: 1 }],
    });
  });

  it("does not render an Offer checkbox — it's automatic, not configurable", () => {
    const onChange = vi.fn();
    renderEditor({ stages: [] }, onChange);
    expect(
      screen.queryByRole("checkbox", { name: "Offer" }),
    ).not.toBeInTheDocument();
  });

  it("edits rounds for an included stage", async () => {
    const onChange = vi.fn();
    renderEditor({ stages: [{ stage: "tech", rounds: 1 }] }, onChange);
    fireEvent.change(screen.getByLabelText("tech sessions"), {
      target: { value: "3" },
    });
    expect(onChange).toHaveBeenCalledWith({
      stages: [{ stage: "tech", rounds: 3 }],
    });
  });

  it("clamps rounds to >= 1 when user enters 0 or negative", () => {
    const onChange = vi.fn();
    renderEditor({ stages: [{ stage: "tech", rounds: 1 }] }, onChange);
    fireEvent.change(screen.getByLabelText("tech sessions"), {
      target: { value: "0" },
    });
    expect(onChange).toHaveBeenCalledWith({
      stages: [{ stage: "tech", rounds: 1 }],
    });
  });

  it("drops retired stage keys stored by older postings instead of echoing them back", () => {
    const onChange = vi.fn();
    renderEditor(
      { stages: [{ stage: "tech", rounds: 1, referralSkippable: true }] },
      onChange,
    );
    fireEvent.change(screen.getByLabelText("tech sessions"), {
      target: { value: "2" },
    });
    // The request DTO forbids unknown fields, so a stale key round-tripped
    // out of the stored config would fail the save with a 400.
    expect(onChange).toHaveBeenCalledWith({
      stages: [{ stage: "tech", rounds: 2 }],
    });
  });

  it("shows defaultAssignee only for screening/behavioral and sets it from the pool", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor(
      {
        stages: [
          { stage: "recruiter_screening", rounds: 1 },
          { stage: "tech", rounds: 1 },
        ],
      },
      onChange,
    );
    expect(
      screen.getByRole("combobox", { name: "recruiter_screening assignee" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "tech assignee" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("combobox", { name: "recruiter_screening assignee" }),
    );
    await user.click(screen.getByRole("option", { name: /Ann/ }));
    expect(onChange).toHaveBeenCalledWith({
      stages: [
        {
          stage: "recruiter_screening",
          rounds: 1,
          defaultAssigneeId: 7,
        },
        { stage: "tech", rounds: 1 },
      ],
    });
  });

  it("renders existing owners as chips and adds another from the pool", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ ownerIds: [42], stages: [] }, onChange);
    expect(screen.getByText("Bo")).toBeInTheDocument();
    await user.click(screen.getByRole("combobox", { name: "Add recruiter" }));
    await user.click(screen.getByRole("option", { name: /Cy/ }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ ownerIds: [42, 43] }),
    );
  });

  it("falls back to legacy ownerId and removes an owner via chip x", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ ownerId: 42, stages: [] }, onChange);
    expect(screen.getByText("Bo")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Remove recruiter Bo" }),
    );
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ ownerIds: [] }),
    );
  });

  it("shows an unresolved owner with the unavailable suffix", () => {
    const onChange = vi.fn();
    renderEditor({ ownerIds: [99], stages: [] }, onChange);
    expect(screen.getByText("User 99 — unavailable")).toBeInTheDocument();
  });

  it("does not offer an already-selected owner in the add-owner pool", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderEditor({ ownerIds: [42, 43], stages: [] }, onChange);
    await user.click(screen.getByRole("combobox", { name: "Add recruiter" }));
    expect(
      screen.queryByRole("option", { name: /Bo/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: /Cy/ }),
    ).not.toBeInTheDocument();
  });
});
