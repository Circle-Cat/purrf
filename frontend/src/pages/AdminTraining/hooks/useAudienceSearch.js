import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  assignCourseBulk,
  listAudienceIds,
  searchAudience,
} from "@/api/trainingApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";
import { defaultCourseStatusFor } from "@/pages/AdminTraining/utils";

const LIMIT = 20;

/** Empty facets read as "no constraint", which the API wants as absent. */
const orUndefined = (value) => (value === "" ? undefined : value);

const facetParams = (query) => ({
  search: orUndefined(query.search),
  userId: orUndefined(query.userId),
  userType: orUndefined(query.userType),
  group: orUndefined(query.group),
  mentorshipRole: orUndefined(query.mentorshipRole),
  courseId: orUndefined(query.courseId),
  courseStatus: orUndefined(query.courseStatus),
});

const EMPTY_QUERY = {
  search: "",
  userId: "",
  userType: "",
  group: "",
  mentorshipRole: "",
  courseId: "",
  courseStatus: "",
};

/** Whether two facet sets ask the same question. */
const sameFacets = (left, right) =>
  Object.keys(EMPTY_QUERY).every((key) => left[key] === right[key]);

/**
 * The person search behind the Assign training card: draft facets, a
 * committed query, one page of results, a selection that outlives paging,
 * and the batch that assigns it.
 *
 * Nothing is read until the search is submitted. An unnarrowed search is a
 * legitimate query -- everyone active, no course in scope -- but it is the
 * whole company, so it is asked for rather than assumed. Assign stays
 * disabled until a course is named.
 *
 * @param {{courses: Array<{courseId: number, liveState: string, isActive: boolean}>}} params
 *   every course in the catalogue, deactivated and packageless included: they
 *   still carry learners, and hiding them would hide those people.
 * @returns {Object} the facets and their setters, the page, the selection,
 *   and `assign`.
 */
export function useAudienceSearch({ courses }) {
  const [draft, setDraft] = useState(EMPTY_QUERY);
  // null until the first submit: no query, nothing fetched, empty screen.
  const [query, setQuery] = useState(null);
  const [deadline, setDeadline] = useState("");

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);

  const [selected, setSelected] = useState(() => new Set());
  const [assigning, setAssigning] = useState(false);

  const { begin, isCurrent } = useRequestGuard();

  // Every facet edit drops the ticks: a cohort ticked against one result set
  // must never be assignable against another.
  const editFacet = useCallback((changes) => {
    setSelected(new Set());
    setDraft((current) => ({ ...current, ...changes }));
  }, []);

  const selectedCourse = useMemo(
    () =>
      courses.find((course) => String(course.courseId) === draft.courseId) ??
      null,
    [courses, draft.courseId],
  );

  const setSearch = useCallback(
    (value) => editFacet({ search: value }),
    [editFacet],
  );
  const setUserId = useCallback(
    (value) => editFacet({ userId: value }),
    [editFacet],
  );
  const setMentorshipRole = useCallback(
    (value) => editFacet({ mentorshipRole: value }),
    [editFacet],
  );
  const setGroup = useCallback(
    (value) => editFacet({ group: value }),
    [editFacet],
  );

  // A group exists only for somebody with a company account, so leaving one
  // set behind a disabled control would keep a filter that is applied but no
  // longer shown -- and under-assign without saying so.
  const setUserType = useCallback(
    (value) =>
      editFacet(
        value === "internal"
          ? { userType: value }
          : { userType: value, group: "" },
      ),
    [editFacet],
  );

  // The course-status facet has nothing to be about without a course, so it
  // resets with the same rule rather than staying set out of sight.
  const setCourseId = useCallback(
    (value) => {
      const course =
        courses.find((candidate) => String(candidate.courseId) === value) ??
        null;
      editFacet({
        courseId: value,
        courseStatus: defaultCourseStatusFor(course),
      });
    },
    [courses, editFacet],
  );

  const setCourseStatus = useCallback(
    (value) => editFacet({ courseStatus: value }),
    [editFacet],
  );

  const fetchPage = useCallback(async () => {
    if (query === null) return;
    const sequence = begin();
    setLoading(true);
    try {
      const { data } = await searchAudience({
        ...facetParams(query),
        limit: LIMIT,
        offset,
      });
      if (!isCurrent(sequence)) return;
      setRows(data?.rows ?? []);
      setTotal(data?.total ?? 0);
    } catch (error) {
      if (!isCurrent(sequence)) return;
      setRows([]);
      setTotal(0);
      toast.error(error.message);
    } finally {
      if (isCurrent(sequence)) setLoading(false);
    }
  }, [begin, isCurrent, offset, query]);

  useEffect(() => {
    fetchPage();
  }, [fetchPage]);

  const submitSearch = useCallback(() => {
    setSelected(new Set());
    setOffset(0);
    setQuery(draft);
  }, [draft]);

  const nextPage = useCallback(
    () =>
      setOffset((current) =>
        current + LIMIT < total ? current + LIMIT : current,
      ),
    [total],
  );
  const prevPage = useCallback(
    () => setOffset((current) => Math.max(0, current - LIMIT)),
    [],
  );

  const toggleSelected = useCallback((userId, checked) => {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(userId);
      else next.delete(userId);
      return next;
    });
  }, []);

  const togglePage = useCallback(
    (checked) => {
      setSelected((current) => {
        const next = new Set(current);
        for (const row of rows) {
          if (checked) next.add(row.userId);
          else next.delete(row.userId);
        }
        return next;
      });
    },
    [rows],
  );

  // A separate request for ids alone, not a select-all over the page: the
  // ticks are what gets submitted, so they have to cover every match. The
  // API refuses a result set too large to hold rather than trimming it, and
  // that refusal is the operator's answer -- the selection stays as it was.
  const selectAllMatching = useCallback(async () => {
    try {
      const { data } = await listAudienceIds(facetParams(query));
      setSelected(new Set(data?.userIds ?? []));
    } catch (error) {
      toast.error(error.message);
    }
  }, [query]);

  const clearSelection = useCallback(() => setSelected(new Set()), []);

  const selectedIds = useMemo(
    () => [...selected].sort((left, right) => left - right),
    [selected],
  );

  const assign = useCallback(async () => {
    if (!selectedCourse || selectedIds.length === 0) return;
    setAssigning(true);
    try {
      const response = await assignCourseBulk({
        courseId: selectedCourse.courseId,
        userIds: selectedIds,
        // Absent, not empty: the request DTO rejects an empty string, and a
        // course with no deadline is the ordinary case.
        ...(deadline ? { deadline } : {}),
      });
      toast.success(response?.message ?? "Training assigned.");
      setSelected(new Set());
      await fetchPage();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setAssigning(false);
    }
  }, [deadline, fetchPage, selectedCourse, selectedIds]);

  return {
    search: draft.search,
    setSearch,
    userId: draft.userId,
    setUserId,
    userType: draft.userType,
    setUserType,
    group: draft.group,
    setGroup,
    groupDisabled: draft.userType !== "internal",
    mentorshipRole: draft.mentorshipRole,
    setMentorshipRole,
    courseId: draft.courseId,
    setCourseId,
    courseStatus: draft.courseStatus,
    setCourseStatus,
    courseStatusDisabled: draft.courseId === "",
    hasSearched: query !== null,
    // The course the rows on screen were actually fetched for. The draft can
    // already name another one -- picking a course does not refetch -- and a
    // column that followed the draft would claim a status nobody asked the
    // server about.
    resultsCourseId: query?.courseId ?? "",
    // Facets edited since the last search: the rows, the total and the ids
    // behind "select all" all still answer the previous question.
    facetsEdited: query !== null && !sameFacets(draft, query),
    selectedCourse,
    deadline,
    setDeadline,
    submitSearch,
    rows,
    total,
    loading,
    limit: LIMIT,
    offset,
    nextPage,
    prevPage,
    selectedIds,
    toggleSelected,
    togglePage,
    selectAllMatching,
    clearSelection,
    assign,
    assigning,
  };
}
