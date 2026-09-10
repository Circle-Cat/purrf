import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import AudienceTable from "@/pages/AdminTraining/components/AudienceTable";
import { useAudienceSearch } from "@/pages/AdminTraining/hooks/useAudienceSearch";
import { bulkAssignBlockedReason } from "@/pages/AdminTraining/utils";

const SELECT_CLASS =
  "rounded-md border border-slate-300 bg-white p-2 text-sm text-slate-900 disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Search the company for people and give a course to as many of them as
 * match. The first-login dispatch only ever reaches somebody signing in for
 * the first time, so this card is how everybody already on the books is
 * topped up after a mandatory course is published.
 *
 * Nothing here is scoped to a course by default: the same search answers
 * "who is missing this course" and "what does this person hold", and only
 * the first of those needs a course named. Assign stays disabled until one is.
 *
 * The table stays empty until the search is submitted. An unnarrowed search
 * is allowed, but it is the whole company, so it is asked for rather than
 * run on arrival.
 *
 * @param {Object} props
 * @param {Array<Object>} props.courses every course in the catalogue,
 *   deactivated and packageless ones included -- they still carry learners,
 *   and filtering them out of the dropdown would hide those people.
 */
export default function AssignTrainingCard({ courses }) {
  const audience = useAudienceSearch({ courses });
  const blockedReason = bulkAssignBlockedReason(audience.selectedCourse);
  const selectedCount = audience.selectedIds.length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Assign training
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="audience-course">Target course</Label>
            <select
              id="audience-course"
              className={SELECT_CLASS}
              value={audience.courseId}
              onChange={(event) => audience.setCourseId(event.target.value)}
            >
              <option value="">All courses</option>
              {courses.map((course) => (
                <option key={course.courseId} value={String(course.courseId)}>
                  {course.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="audience-search">Name or email</Label>
            <Input
              id="audience-search"
              className="w-72"
              value={audience.search}
              placeholder="Name or email address"
              onChange={(event) => audience.setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") audience.submitSearch();
              }}
            />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="audience-user-id">User ID</Label>
            <Input
              id="audience-user-id"
              className="w-28"
              inputMode="numeric"
              value={audience.userId}
              onChange={(event) =>
                audience.setUserId(event.target.value.replace(/\D/g, ""))
              }
            />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="audience-type">Type</Label>
            <select
              id="audience-type"
              className={SELECT_CLASS}
              value={audience.userType}
              onChange={(event) => audience.setUserType(event.target.value)}
            >
              <option value="">All types</option>
              <option value="internal">Internal</option>
              <option value="external">External</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="audience-group">Group</Label>
            <select
              id="audience-group"
              className={SELECT_CLASS}
              value={audience.group}
              disabled={audience.groupDisabled}
              title={
                audience.groupDisabled
                  ? "A group only exists for an internal account"
                  : undefined
              }
              onChange={(event) => audience.setGroup(event.target.value)}
            >
              <option value="">All groups</option>
              <option value="interns">Interns</option>
              <option value="employees">Employees</option>
              <option value="volunteers">Volunteers</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="audience-mentorship">Mentorship</Label>
            <select
              id="audience-mentorship"
              className={SELECT_CLASS}
              value={audience.mentorshipRole}
              onChange={(event) =>
                audience.setMentorshipRole(event.target.value)
              }
            >
              <option value="">All roles</option>
              <option value="mentor">Mentor</option>
              <option value="mentee">Mentee</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="audience-course-status">On this course</Label>
            <select
              id="audience-course-status"
              className={SELECT_CLASS}
              value={audience.courseStatus}
              disabled={audience.courseStatusDisabled}
              title={
                audience.courseStatusDisabled
                  ? "Pick a course to filter by"
                  : undefined
              }
              onChange={(event) => audience.setCourseStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="assigned">Assigned</option>
              <option value="not_assigned">Not assigned</option>
            </select>
          </div>

          <Button type="button" onClick={audience.submitSearch}>
            Search
          </Button>
        </div>

        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={audience.total === 0 || audience.facetsEdited}
              title={
                audience.facetsEdited
                  ? "Search again before selecting everyone"
                  : undefined
              }
              onClick={audience.selectAllMatching}
            >
              {`Select all ${audience.total} matching`}
            </Button>
            <span>{`${selectedCount} selected`}</span>
            {selectedCount > 0 && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={audience.clearSelection}
              >
                Clear
              </Button>
            )}
          </div>

          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="audience-deadline">Deadline (optional)</Label>
              <Input
                id="audience-deadline"
                type="date"
                className="w-44"
                value={audience.deadline}
                onChange={(event) => audience.setDeadline(event.target.value)}
              />
            </div>
            <Button
              type="button"
              title={blockedReason ?? undefined}
              disabled={
                blockedReason !== null ||
                selectedCount === 0 ||
                audience.assigning
              }
              onClick={audience.assign}
            >
              Assign
            </Button>
          </div>
        </div>

        {!audience.hasSearched ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Search to find the people to assign a course to.
          </p>
        ) : audience.loading && audience.rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : audience.rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Nobody matches this search.
          </p>
        ) : (
          <AudienceTable
            rows={audience.rows}
            courseScoped={audience.resultsCourseId !== ""}
            selectedIds={audience.selectedIds}
            onToggle={audience.toggleSelected}
            onTogglePage={audience.togglePage}
            total={audience.total}
            limit={audience.limit}
            offset={audience.offset}
            onPrev={audience.prevPage}
            onNext={audience.nextPage}
          />
        )}
      </CardContent>
    </Card>
  );
}
