import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import ApplicantSearch from "@/pages/Recruiting/board/ApplicantSearch";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => {
  vi.clearAllMocks();
});

const hit = (overrides = {}) => ({
  applicationId: 10,
  applicantName: "Zhang Wei",
  applicantEmail: "zw@example.com",
  jobId: 1,
  jobTitle: "Backend Engineer",
  jobKind: "employment",
  stage: "tech",
  appliedAt: "2026-01-01T00:00:00Z",
  ...overrides,
});

const renderSearch = (props = {}) =>
  render(<ApplicantSearch selectedJobId={1} onSelect={vi.fn()} {...props} />);

const typeTerm = async (user, term) =>
  user.type(screen.getByPlaceholderText("Search by name or email"), term);

describe("ApplicantSearch", () => {
  it("fires no request while typing", async () => {
    const user = userEvent.setup();
    renderSearch();

    await typeTerm(user, "zhang");

    expect(api.searchBoardApplicants).not.toHaveBeenCalled();
  });

  it("searches the selected job when All postings is off", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit()], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(api.searchBoardApplicants).toHaveBeenCalledTimes(1);
    });
    expect(api.searchBoardApplicants).toHaveBeenCalledWith("zhang", {
      jobId: 1,
      currentJobId: 1,
    });
  });

  it("drops the job scope when All postings is on", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [], truncated: false },
    });
    renderSearch();

    await user.click(screen.getByLabelText("All postings"));
    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(api.searchBoardApplicants).toHaveBeenCalledWith("zhang", {
        jobId: null,
        currentJobId: 1,
      });
    });
  });

  it("submits on Enter in the input", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang{Enter}");

    await waitFor(() => {
      expect(api.searchBoardApplicants).toHaveBeenCalledTimes(1);
    });
  });

  it("disables Search until the term has non-whitespace", async () => {
    const user = userEvent.setup();
    renderSearch();

    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();

    await typeTerm(user, "   ");
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();

    await typeTerm(user, "z");
    expect(screen.getByRole("button", { name: "Search" })).toBeEnabled();
  });

  it("fires no request when All postings is toggled on its own", async () => {
    const user = userEvent.setup();
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByLabelText("All postings"));

    expect(api.searchBoardApplicants).not.toHaveBeenCalled();
  });

  it("disables Search while a request is in flight", async () => {
    const user = userEvent.setup();
    let release;
    api.searchBoardApplicants.mockReturnValue(
      new Promise((resolve) => {
        release = () => resolve({ data: { hits: [], truncated: false } });
      }),
    );
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();

    release();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Search" })).toBeEnabled();
    });
  });

  it("keeps the previous results on screen while the term is edited", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit()], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("option")).toBeInTheDocument();

    await typeTerm(user, "xyz");

    // No invalidate-on-keystroke: the panel still shows the last search until
    // Search runs again.
    expect(screen.getByRole("option")).toBeInTheDocument();
    expect(api.searchBoardApplicants).toHaveBeenCalledTimes(1);
  });

  it("renders name, email and stage on each row", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit()], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    const row = await screen.findByRole("option");
    expect(within(row).getByText("Zhang Wei")).toBeInTheDocument();
    expect(row).toHaveTextContent("zw@example.com");
    expect(row).toHaveTextContent("Tech");
  });

  it("shows the job title only in All postings mode", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit()], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("option")).not.toHaveTextContent(
      "Backend Engineer",
    );

    await user.click(screen.getByLabelText("All postings"));
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => {
      expect(screen.getByRole("option")).toHaveTextContent("Backend Engineer");
    });
  });

  it("labels an activity job's hired stage as Admitted", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: {
        hits: [hit({ jobId: 2, jobKind: "activity", stage: "hired" })],
        truncated: false,
      },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByRole("option")).toHaveTextContent("Admitted");
  });

  it("calls onSelect with the application id when a row is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit({ applicationId: 42 })], truncated: false },
    });
    renderSearch({ onSelect });

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("option"));

    expect(onSelect).toHaveBeenCalledWith(42);
  });

  it("shows No matches for an empty result", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("No matches")).toBeInTheDocument();
  });

  it("shows the truncation notice derived from the actual number of hits rendered", async () => {
    const user = userEvent.setup();
    // 7 hits, not 1: proves the count tracks result.hits.length rather than
    // a hardcoded cap that happens to still read "20" today.
    const hits = Array.from({ length: 7 }, (_, i) =>
      hit({ applicationId: i + 1 }),
    );
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits, truncated: true },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findAllByRole("option")).toHaveLength(7);
    expect(
      screen.getByText("Showing first 7 matches — refine your search"),
    ).toBeInTheDocument();
  });

  it("toasts and keeps the panel closed when the request fails", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockRejectedValue(new Error("boom"));
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("boom");
    });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes an open results panel when a subsequent search fails", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValueOnce({
      data: { hits: [hit()], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("option")).toBeInTheDocument();

    api.searchBoardApplicants.mockRejectedValueOnce(new Error("boom"));
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("boom");
    });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("reflects aria-expanded on the input before and after a search opens the panel", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit()], truncated: false },
    });
    renderSearch();

    const input = screen.getByPlaceholderText("Search by name or email");
    expect(input).toHaveAttribute("aria-expanded", "false");

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByRole("option");

    expect(input).toHaveAttribute("aria-expanded", "true");
  });

  it("points aria-controls at the listbox's actual id", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit()], truncated: false },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    const listbox = await screen.findByRole("listbox");

    const input = screen.getByPlaceholderText("Search by name or email");
    expect(input.getAttribute("aria-controls")).toBe(
      listbox.getAttribute("id"),
    );
  });

  it("sets aria-activedescendant to the highlighted option's id, and clears it when nothing is highlighted", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: {
        hits: [hit({ applicationId: 10 }), hit({ applicationId: 11 })],
        truncated: false,
      },
    });
    renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    const options = await screen.findAllByRole("option");

    const input = screen.getByPlaceholderText("Search by name or email");
    // Nothing highlighted yet: the attribute must be absent, not merely
    // an empty string.
    expect(input).not.toHaveAttribute("aria-activedescendant");

    await user.keyboard("{ArrowDown}");

    expect(input.getAttribute("aria-activedescendant")).toBe(
      options[0].getAttribute("id"),
    );
  });

  it("clears results when the job changes", async () => {
    const user = userEvent.setup();
    api.searchBoardApplicants.mockResolvedValue({
      data: { hits: [hit()], truncated: false },
    });
    const { rerender } = renderSearch();

    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("option")).toBeInTheDocument();

    rerender(<ApplicantSearch selectedJobId={2} onSelect={vi.fn()} />);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search by name or email")).toHaveValue(
      "",
    );
  });
});

describe("ApplicantSearch keyboard and dismissal", () => {
  const openPanelWithTwoHits = async (user, onSelect = vi.fn()) => {
    api.searchBoardApplicants.mockResolvedValue({
      data: {
        hits: [hit({ applicationId: 10 }), hit({ applicationId: 11 })],
        truncated: false,
      },
    });
    render(
      <div>
        <ApplicantSearch selectedJobId={1} onSelect={onSelect} />
        <button type="button">outside</button>
      </div>,
    );
    await typeTerm(user, "zhang");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await screen.findAllByRole("option");
    return onSelect;
  };

  it("wraps ArrowDown from the last row back to the top", async () => {
    const user = userEvent.setup();
    const onSelect = await openPanelWithTwoHits(user);

    // Three presses over two hits: 0, 1, wrap back to 0. A clamp instead of
    // a modulo would stall at index 1 (id 11) instead of wrapping to id 10.
    await user.keyboard("{ArrowDown}{ArrowDown}{ArrowDown}{Enter}");

    expect(onSelect).toHaveBeenCalledWith(10);
  });

  it("wraps ArrowUp from the top to the last row", async () => {
    const user = userEvent.setup();
    const onSelect = await openPanelWithTwoHits(user);

    await user.keyboard("{ArrowUp}{Enter}");

    expect(onSelect).toHaveBeenCalledWith(11);
  });

  it("Enter re-runs the search when no row is highlighted", async () => {
    const user = userEvent.setup();
    await openPanelWithTwoHits(user);

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(api.searchBoardApplicants).toHaveBeenCalledTimes(2);
    });
  });

  it("closes the panel on Escape and returns focus to the input", async () => {
    const user = userEvent.setup();
    await openPanelWithTwoHits(user);

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Search by name or email"),
    ).toHaveFocus();
  });

  it("closes the panel when clicking outside it", async () => {
    const user = userEvent.setup();
    await openPanelWithTwoHits(user);

    await user.click(screen.getByRole("button", { name: "outside" }));

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes the panel when the input is cleared", async () => {
    const user = userEvent.setup();
    await openPanelWithTwoHits(user);

    await user.clear(screen.getByPlaceholderText("Search by name or email"));

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
