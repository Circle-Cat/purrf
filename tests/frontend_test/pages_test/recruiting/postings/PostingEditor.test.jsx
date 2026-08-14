import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import PostingEditor from "@/pages/Recruiting/postings/PostingEditor";
import * as api from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/api/recruitingApi");

// In the Bazel sandbox, vi.mock("sonner", factory) does not intercept the module
// that the component resolves at import time (same module-resolution issue as
// react-router-dom).  Follow the established codebase pattern: import the real
// toast and spy on its methods.
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

// react-router-dom re-exports live hooks from react-router; in the Bazel sandbox
// vi.mock("react-router-dom") alone does not intercept useNavigate/useParams for
// the component.  Use createMemoryRouter + RouterProvider so both hooks work.

beforeEach(() => {
  vi.clearAllMocks();
  api.createJob.mockResolvedValue({ data: { id: 1 } });
  api.updateJob.mockResolvedValue({ data: { id: 1 } });
  api.getJob.mockResolvedValue({
    data: {
      id: 5,
      title: "Loaded",
      description: "",
      kind: "activity",
      cooldownDays: null,
      formSchema: { questions: [] },
      pipelineConfig: { ownerId: 9, stages: [] },
    },
  });
  api.listInterviewPool.mockResolvedValue({ data: [] });
  api.listJobOwners.mockResolvedValue({ data: [] });
});

/** Render PostingEditor inside a MemoryRouter at the given path.
 * Returns both the render result and a handle to the router so tests can
 * inspect router.state.location after navigation. */
const renderAt = (path) => {
  const router = createMemoryRouter(
    [
      { path: "*", element: <PostingEditor /> },
      { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
    ],
    { initialEntries: [path] },
  );
  const result = render(<RouterProvider router={router} />);
  return { ...result, router };
};

describe("PostingEditor", () => {
  it("labels every section of the form with its own explanation", async () => {
    renderAt("/postings/new");

    for (const heading of [
      "Basics",
      "Application form",
      "Interview pipeline",
      "Machine screening",
      "Profile requirements",
    ]) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
    expect(
      screen.queryByRole("button", { name: "How it works" }),
    ).not.toBeInTheDocument();

    (await screen.findByText("Interview pipeline")).focus();

    expect(
      await screen.findByText(
        "Pick one or more recruiters -- staff who can advance applicants through every stage of this posting -- then add the stages applicants move through, in order. A stage can require several sessions.",
      ),
    ).toBeInTheDocument();
  });

  it("says that editing a live posting only stages the change", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Loaded",
        description: "",
        kind: "activity",
        status: "published",
        cooldownDays: null,
        formSchema: { questions: [] },
        pipelineConfig: { ownerId: 9, stages: [] },
      },
    });
    const router = createMemoryRouter(
      [{ path: "/postings/:id/edit", element: <PostingEditor /> }],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);

    expect(
      await screen.findByText(/Saving stages your change/),
    ).toBeInTheDocument();
  });

  it("says nothing about staging on a draft, which has nothing live to protect", async () => {
    const router = createMemoryRouter(
      [{ path: "/postings/:id/edit", element: <PostingEditor /> }],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    await screen.findByDisplayValue("Loaded");

    expect(
      screen.queryByText(/Saving stages your change/),
    ).not.toBeInTheDocument();
  });

  it("says above the buttons that saving does not publish", () => {
    renderAt("/postings/new");
    expect(screen.getByText(/Saving never publishes\./)).toBeInTheDocument();
  });

  // Same column as the preview box, not a separate footer below the whole
  // form -- so the buttons always sit right under it.
  it("renders Cancel and Save inside the preview column", () => {
    renderAt("/postings/new");
    const previewColumn = screen.getByText("Preview").parentElement;
    for (const name of ["Cancel", "Save"]) {
      expect(previewColumn).toContainElement(
        screen.getByRole("button", { name }),
      );
    }
  });

  it("does not send a draft that fails validation", async () => {
    // The API answers a bad draft with one sentence naming an internal
    // question id; catching it here is what lets the page point at the field.
    renderAt("/postings/new");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(screen.getByText("Title is required")).toBeInTheDocument(),
    );
    expect(api.createJob).not.toHaveBeenCalled();
  });

  it("clears an error as soon as its field is fixed", async () => {
    renderAt("/postings/new");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(screen.getByText("Title is required")).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE" },
    });
    await waitFor(() =>
      expect(screen.queryByText("Title is required")).not.toBeInTheDocument(),
    );
  });

  it("does not turn the page red before the author tries to save", () => {
    // Errors are only ever cleared while typing, never added, so a
    // half-finished question does not light up mid-keystroke.
    renderAt("/postings/new");
    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("creates a new posting from the typed draft", async () => {
    const { router } = renderAt("/postings/new");
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.createJob).toHaveBeenCalled());
    expect(api.createJob.mock.calls[0][0]).toMatchObject({
      title: "SWE",
      kind: "activity",
      cooldownDays: 0,
      mentorshipRole: null,
      formSchema: { questions: [] },
    });
    expect(toast.success).toHaveBeenCalled();
    // Straight to the new posting's page: Submit for review lives there, and
    // the author has nothing left to do on the list they came from.
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        ROUTE_PATHS.RECRUITING_POSTING_DETAIL(1),
      ),
    );
  });

  it("loads an existing posting and updates it, preserving untouched config", async () => {
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByDisplayValue("Loaded")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());
    const [jobId, body] = api.updateJob.mock.calls[0];
    expect(jobId).toBe("5");
    expect(body.pipelineConfig).toEqual({ ownerId: 9, stages: [] });
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        ROUTE_PATHS.RECRUITING_POSTING_DETAIL("5"),
      ),
    );
  });

  it("prefills from pendingPayload when a CLOSED posting already has a staged edit", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Live title",
        description: "",
        kind: "activity",
        cooldownDays: null,
        formSchema: { questions: [] },
        pipelineConfig: { ownerId: 9, stages: [] },
        pendingPayload: {
          title: "Staged title",
          description: "Staged description",
          cooldownDays: 30,
          formSchema: { questions: [] },
          pipelineConfig: { ownerId: 9, stages: [] },
        },
      },
    });
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByDisplayValue("Staged title")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Staged description")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());
    expect(api.updateJob.mock.calls[0][1]).toMatchObject({
      title: "Staged title",
      cooldownDays: 30,
    });
  });

  it("preserves a multi-owner pipeline config untouched through save", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Loaded",
        description: "",
        kind: "activity",
        cooldownDays: null,
        formSchema: { questions: [] },
        pipelineConfig: { ownerIds: [9, 10], stages: [] },
      },
    });
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByDisplayValue("Loaded")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());
    const [, body] = api.updateJob.mock.calls[0];
    expect(body.pipelineConfig).toEqual({ ownerIds: [9, 10], stages: [] });
  });

  it("loads an employment posting's cooldown and saves the edited value", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Eng",
        description: "",
        kind: "employment",
        cooldownDays: 45,
        formSchema: { questions: [] },
      },
    });
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    const input = await screen.findByLabelText("Cooldown days");
    // `findByLabelText` resolves as soon as the input exists in the DOM,
    // but its value is populated by a later render once the loaded job
    // data flows into form state — wait for the value itself, not just
    // the element's presence, to avoid a race under slower test runs.
    await waitFor(() => expect(input.value).toBe("45"));
    fireEvent.change(input, { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());
    expect(api.updateJob.mock.calls[0][1].cooldownDays).toBe(30);
  });

  it("loads an activity posting's mentorship role and saves the edited value", async () => {
    const user = userEvent.setup();
    api.getJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Mentor gig",
        description: "",
        kind: "activity",
        mentorshipRole: "mentor",
        formSchema: { questions: [] },
      },
    });
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByDisplayValue("Mentor gig")).toBeInTheDocument();
    const select = screen.getByRole("combobox", { name: "Mentorship role" });
    // Same race as the cooldown test above: the select exists as soon as
    // the form renders, but its displayed text is populated by a later
    // render once the loaded mentorshipRole flows into form state.
    await waitFor(() => expect(select).toHaveTextContent("Mentor"));
    await user.click(select);
    await user.click(screen.getByRole("option", { name: "Mentee" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());
    expect(api.updateJob.mock.calls[0][1].mentorshipRole).toBe("mentee");
  });

  it("shows the backend error message on save failure", async () => {
    api.createJob.mockRejectedValue(new Error("bad form"));
    renderAt("/postings/new");
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "X" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("bad form"));
  });

  it("fetches both pools on mount and saves edited config", async () => {
    api.listInterviewPool.mockResolvedValue({
      data: [{ userId: 7, name: "Ann", email: "ann@x.com" }],
    });
    api.listJobOwners.mockResolvedValue({
      data: [{ userId: 42, name: "Bo", email: "bo@x.com" }],
    });
    const user = userEvent.setup();
    renderAt("/postings/new");
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    expect(api.listJobOwners).toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "T" },
    });
    // tick a pipeline stage so the saved payload carries pipelineConfig
    await user.click(screen.getByRole("checkbox", { name: "Tech" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.createJob).toHaveBeenCalled());
    expect(api.createJob.mock.calls[0][0].pipelineConfig.stages).toEqual([
      { stage: "tech", rounds: 1 },
    ]);
  });

  it("disables Save and shows Saving… while the create request is in flight", async () => {
    let resolveCreate;
    api.createJob.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );
    const { router } = renderAt("/postings/new");
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    const savingBtn = await screen.findByRole("button", { name: "Saving…" });
    expect(savingBtn).toBeDisabled();

    resolveCreate({ data: { id: 1 } });
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        ROUTE_PATHS.RECRUITING_POSTING_DETAIL(1),
      ),
    );
  });

  it("previews the applicant-facing view as the draft changes", () => {
    renderAt("/postings/new");
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE" },
    });
    expect(screen.getByRole("heading", { name: "SWE" })).toBeInTheDocument();
  });

  it("locks Posting type once a loaded posting is no longer a draft", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Loaded",
        description: "",
        kind: "activity",
        status: "published",
        cooldownDays: null,
        formSchema: { questions: [] },
      },
    });
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByDisplayValue("Loaded")).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Posting type" }),
    ).toBeDisabled();
  });

  it("leaves Posting type editable for a draft posting", async () => {
    api.getJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Loaded",
        description: "",
        kind: "activity",
        status: "draft",
        cooldownDays: null,
        formSchema: { questions: [] },
      },
    });
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByDisplayValue("Loaded")).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Posting type" }),
    ).not.toBeDisabled();
  });

  it("leaves Posting type editable for a brand-new posting", () => {
    renderAt("/postings/new");
    expect(
      screen.getByRole("combobox", { name: "Posting type" }),
    ).not.toBeDisabled();
  });

  it("defaults the Cooldown days field to 0 on a new posting", () => {
    renderAt("/postings/new");
    expect(screen.getByLabelText("Cooldown days").value).toBe("0");
  });

  it("shows 0 when loading an existing posting whose cooldown is unset", async () => {
    // beforeEach mocks getJob with cooldownDays: null; the load fallback
    // (`source.cooldownDays ?? 0`) must render it as "0", not blank.
    const router = createMemoryRouter(
      [
        { path: "/postings/:id/edit", element: <PostingEditor /> },
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <div /> },
      ],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    const input = await screen.findByLabelText("Cooldown days");
    await waitFor(() => expect(input.value).toBe("0"));
  });
});
