import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { useAudienceSearch } from "@/pages/AdminTraining/hooks/useAudienceSearch";
import {
  searchAudience,
  listAudienceIds,
  assignCourseBulk,
} from "@/api/trainingApi";

vi.mock("@/api/trainingApi", () => ({
  searchAudience: vi.fn(),
  listAudienceIds: vi.fn(),
  assignCourseBulk: vi.fn(),
}));

const LIVE_COURSE = {
  courseId: 1,
  name: "Corporate Culture",
  liveState: "live",
  isActive: true,
};
const DEACTIVATED_COURSE = {
  courseId: 2,
  name: "Old Safety Briefing",
  liveState: "live",
  isActive: false,
};
const COURSES = [LIVE_COURSE, DEACTIVATED_COURSE];

const page = (
  rows = [{ userId: 11 }, { userId: 12 }],
  total = rows.length,
) => ({
  data: { rows, total },
});

const render = () => renderHook(() => useAudienceSearch({ courses: COURSES }));

/** Renders, submits the search, and waits for the page to land. */
const searched = async (expectedTotal = 2) => {
  const view = render();
  act(() => view.result.current.submitSearch());
  await waitFor(() => expect(view.result.current.total).toBe(expectedTotal));
  return view;
};

describe("useAudienceSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchAudience.mockResolvedValue(page());
    listAudienceIds.mockResolvedValue({
      data: { userIds: [11, 12], total: 2 },
    });
    assignCourseBulk.mockResolvedValue({
      data: { courseId: 1, createdCount: 2, alreadyAssignedCount: 0 },
    });
    vi.spyOn(toast, "error").mockImplementation(() => {});
    vi.spyOn(toast, "success").mockImplementation(() => {});
  });

  it("asks nothing of the server until the search is submitted", async () => {
    const { result } = render();

    await act(async () => {});

    expect(searchAudience).not.toHaveBeenCalled();
    expect(result.current.hasSearched).toBe(false);
    expect(result.current.rows).toEqual([]);
  });

  it("searches with no course in scope when nothing was narrowed", async () => {
    const { result } = await searched();

    expect(result.current.hasSearched).toBe(true);
    expect(searchAudience).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 20, offset: 0 }),
    );
    const [params] = searchAudience.mock.calls[0];
    expect(params.courseId).toBeUndefined();
    expect(params.courseStatus).toBeUndefined();
  });

  it("defaults the course-status facet to the people missing an assignable course", async () => {
    const { result } = await searched();

    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));

    expect(result.current.courseStatus).toBe("not_assigned");
    expect(result.current.courseStatusDisabled).toBe(false);
  });

  it("defaults it to the people already on a course that cannot be assigned", async () => {
    const { result } = await searched();

    act(() => result.current.setCourseId(String(DEACTIVATED_COURSE.courseId)));

    expect(result.current.courseStatus).toBe("assigned");
  });

  it("disables and resets the course-status facet under all courses", async () => {
    const { result } = await searched();
    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));

    act(() => result.current.setCourseId(""));

    expect(result.current.courseStatus).toBe("");
    expect(result.current.courseStatusDisabled).toBe(true);
  });

  it("only offers the group facet to internal accounts", async () => {
    const { result } = await searched();

    expect(result.current.groupDisabled).toBe(true);
    act(() => result.current.setUserType("internal"));
    expect(result.current.groupDisabled).toBe(false);
  });

  it("resets the group when the type moves off internal", async () => {
    const { result } = await searched();
    act(() => result.current.setUserType("internal"));
    act(() => result.current.setGroup("interns"));

    act(() => result.current.setUserType("external"));

    expect(result.current.group).toBe("");
  });

  it("sends the committed facets, camelCased, when the search is submitted", async () => {
    const { result } = render();
    act(() => result.current.setSearch("ada"));
    act(() => result.current.setUserType("internal"));
    act(() => result.current.setGroup("interns"));
    act(() => result.current.setMentorshipRole("mentee"));

    act(() => result.current.submitSearch());

    await waitFor(() =>
      expect(searchAudience).toHaveBeenCalledWith(
        expect.objectContaining({
          search: "ada",
          userType: "internal",
          group: "interns",
          mentorshipRole: "mentee",
          limit: 20,
          offset: 0,
        }),
      ),
    );
  });

  it("holds an edited facet back until the search is submitted again", async () => {
    const { result } = await searched();
    searchAudience.mockClear();

    act(() => result.current.setSearch("ada"));

    expect(searchAudience).not.toHaveBeenCalled();
  });

  it("clears the selection when a facet changes", async () => {
    const { result } = await searched();
    act(() => result.current.toggleSelected(11, true));
    expect(result.current.selectedIds).toEqual([11]);

    act(() => result.current.setSearch("ada"));

    expect(result.current.selectedIds).toEqual([]);
  });

  it("keeps the selection across pages", async () => {
    searchAudience.mockResolvedValue(page([{ userId: 11 }], 40));
    const { result } = await searched(40);
    act(() => result.current.toggleSelected(11, true));

    act(() => result.current.nextPage());
    await waitFor(() => expect(result.current.offset).toBe(20));

    expect(result.current.selectedIds).toEqual([11]);
  });

  it("selects everyone matching through the ids request, not the page", async () => {
    searchAudience.mockResolvedValue(page([{ userId: 11 }], 2));
    const { result } = await searched();

    await act(async () => {
      await result.current.selectAllMatching();
    });

    const [idsParams] = listAudienceIds.mock.calls[0];
    expect(idsParams).not.toHaveProperty("limit");
    expect(idsParams).not.toHaveProperty("offset");
    expect(result.current.selectedIds).toEqual([11, 12]);
  });

  it("reports a refused select-all and leaves the selection alone", async () => {
    const { result } = await searched();
    act(() => result.current.toggleSelected(11, true));
    listAudienceIds.mockRejectedValue(new Error("too many people"));

    await act(async () => {
      await result.current.selectAllMatching();
    });

    expect(toast.error).toHaveBeenCalledWith("too many people");
    expect(result.current.selectedIds).toEqual([11]);
  });

  it("assigns the ticked ids to the course in scope", async () => {
    const { result } = await searched();
    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));
    act(() => result.current.toggleSelected(11, true));
    act(() => result.current.toggleSelected(12, true));

    await act(async () => {
      await result.current.assign();
    });

    expect(assignCourseBulk).toHaveBeenCalledWith({
      courseId: LIVE_COURSE.courseId,
      userIds: [11, 12],
    });
  });

  it("sends a deadline only when one was typed", async () => {
    const { result } = await searched();
    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));
    act(() => result.current.toggleSelected(11, true));
    act(() => result.current.setDeadline("2026-10-01"));

    await act(async () => {
      await result.current.assign();
    });

    expect(assignCourseBulk).toHaveBeenCalledWith({
      courseId: LIVE_COURSE.courseId,
      userIds: [11],
      deadline: "2026-10-01",
    });
  });

  it("clears the selection and reloads the page after assigning", async () => {
    const { result } = await searched();
    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));
    act(() => result.current.toggleSelected(11, true));
    searchAudience.mockClear();

    await act(async () => {
      await result.current.assign();
    });

    expect(result.current.selectedIds).toEqual([]);
    expect(searchAudience).toHaveBeenCalled();
  });

  it("keeps the selection when assigning fails", async () => {
    assignCourseBulk.mockRejectedValue(new Error("nothing published yet"));
    const { result } = await searched();
    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));
    act(() => result.current.toggleSelected(11, true));

    await act(async () => {
      await result.current.assign();
    });

    expect(toast.error).toHaveBeenCalledWith("nothing published yet");
    expect(result.current.selectedIds).toEqual([11]);
  });

  it("reports a failed search and empties the page", async () => {
    searchAudience.mockRejectedValue(new Error("the search broke"));
    const { result } = render();

    act(() => result.current.submitSearch());

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("the search broke"),
    );
    expect(result.current.rows).toEqual([]);
    expect(result.current.total).toBe(0);
  });
  it("keeps the results scoped to the course the rows were fetched for", async () => {
    const { result } = await searched();
    expect(result.current.resultsCourseId).toBe("");

    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));

    // The draft moved; the rows on screen are still the unscoped ones.
    expect(result.current.courseId).toBe(String(LIVE_COURSE.courseId));
    expect(result.current.resultsCourseId).toBe("");
  });

  it("scopes the results once the search is submitted again", async () => {
    const { result } = await searched();
    act(() => result.current.setCourseId(String(LIVE_COURSE.courseId)));

    act(() => result.current.submitSearch());

    await waitFor(() =>
      expect(result.current.resultsCourseId).toBe(String(LIVE_COURSE.courseId)),
    );
  });

  it("reports facets edited since the last search", async () => {
    const { result } = await searched();
    expect(result.current.facetsEdited).toBe(false);

    act(() => result.current.setSearch("ada"));

    expect(result.current.facetsEdited).toBe(true);
  });

  it("stops reporting them once the search is submitted", async () => {
    const { result } = await searched();
    act(() => result.current.setSearch("ada"));

    act(() => result.current.submitSearch());

    await waitFor(() => expect(result.current.facetsEdited).toBe(false));
  });
});
