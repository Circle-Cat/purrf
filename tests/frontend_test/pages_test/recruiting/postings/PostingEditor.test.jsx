import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import PostingEditor from "@/pages/Recruiting/postings/PostingEditor";
import * as api from "@/api/recruitingApi";

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
      formSchema: { questions: [] },
      pipelineConfig: { ownerId: 9, stages: [] },
    },
  });
});

/** Render PostingEditor inside a MemoryRouter at the given path. */
const renderAt = (path) => {
  const router = createMemoryRouter(
    [{ path: "*", element: <PostingEditor /> }],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
};

describe("PostingEditor", () => {
  it("creates a new posting from the typed draft", async () => {
    renderAt("/postings/new");
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.createJob).toHaveBeenCalled());
    expect(api.createJob.mock.calls[0][0]).toMatchObject({
      title: "SWE",
      kind: "activity",
      formSchema: { questions: [] },
    });
    expect(toast.success).toHaveBeenCalled();
  });

  it("loads an existing posting and updates it, preserving untouched config", async () => {
    const router = createMemoryRouter(
      [{ path: "/postings/:id/edit", element: <PostingEditor /> }],
      { initialEntries: ["/postings/5/edit"] },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByDisplayValue("Loaded")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.updateJob).toHaveBeenCalled());
    const [jobId, body] = api.updateJob.mock.calls[0];
    expect(jobId).toBe("5");
    expect(body.pipelineConfig).toEqual({ ownerId: 9, stages: [] });
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
});
