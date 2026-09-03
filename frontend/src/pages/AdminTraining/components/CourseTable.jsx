import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { canAssign, statusLabel } from "@/pages/AdminTraining/utils";
import { updateCourse } from "@/api/trainingApi";
import DeactivateDialog from "@/pages/AdminTraining/components/DeactivateDialog";

// Only the three states with a hosted package get a dot -- External link
// isn't ours to color, it just says where the course actually lives.
const STATE_DOT_COLOR = {
  verified: "var(--stage-hired)",
  needs_trial_run: "var(--stage-tech)",
  no_package: "var(--stage-rejected)",
};

function StatusBadge({ state }) {
  const dotColor = STATE_DOT_COLOR[state];
  return (
    <Badge variant="outline" className="gap-1.5">
      {dotColor && (
        <span
          aria-hidden="true"
          className="size-1.5 rounded-full"
          style={{ backgroundColor: dotColor }}
        />
      )}
      {statusLabel(state)}
    </Badge>
  );
}

// Deactivating stops new assignments only; reactivating undoes that with no
// consequences worth counting, so it needs no confirmation of its own.
function ToggleActiveButton({ course, onDeactivate, onActivate }) {
  if (!course.isActive) {
    return (
      <Button size="sm" variant="ghost" onClick={() => onActivate(course)}>
        Activate
      </Button>
    );
  }
  return (
    <Button size="sm" variant="ghost" onClick={() => onDeactivate(course)}>
      Deactivate
    </Button>
  );
}

// The row's one main action. Assign stays on screen even when it cannot be
// clicked yet -- hiding it would hide the rule (spec §4.1); the hover title
// is the only place that rule is taught, so it isn't optional here.
function RowActions({ course, onDeactivate, onActivate }) {
  const toggle = (
    <ToggleActiveButton
      course={course}
      onDeactivate={onDeactivate}
      onActivate={onActivate}
    />
  );

  if (course.state === "no_package" || course.state === "external_link") {
    return (
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="outline">
          Upload package
        </Button>
        {toggle}
      </div>
    );
  }

  const assignable = canAssign(course);
  return (
    <div className="flex justify-end gap-2">
      {course.state === "needs_trial_run" && (
        <Button size="sm" asChild>
          <Link to={ROUTE_PATHS.TRAINING_TRIAL(course.courseId)}>
            Trial run
          </Link>
        </Button>
      )}
      <Button
        size="sm"
        variant="outline"
        disabled={!assignable}
        title={assignable ? undefined : "Run this course to completion first"}
      >
        Assign
      </Button>
      {toggle}
    </div>
  );
}

function PackageCell({ course }) {
  if (course.link) {
    return (
      <a
        href={course.link}
        target="_blank"
        rel="noreferrer"
        className="text-primary underline-offset-4 hover:underline"
      >
        View ↗
      </a>
    );
  }
  if (course.packageVersion) {
    return (
      <span className="font-mono text-xs text-muted-foreground">
        {course.packageVersion}
      </span>
    );
  }
  return <span className="text-muted-foreground">—</span>;
}

/**
 * The admin course catalogue: Course / Package / Status / Assigned / action.
 *
 * `courses` is the only source of truth for what a row shows -- a mutation
 * never patches it locally, since `assignedCount` and `unfinishedCount` are
 * server-derived aggregates a client-side patch cannot know the true value
 * of. Instead every mutation, on success, calls `onCoursesChanged` and lets
 * the parent refetch and pass fresh `courses` back down.
 *
 * A row's dialog opens by naming the course it is for in one piece of local
 * state (`deactivating` here); the dialog itself is rendered once, outside
 * the row loop, keyed off that state, and closes by setting it back to
 * `null`. Assign and Upload follow the same shape.
 *
 * @param {{courses: Array<Object>, onCoursesChanged: () => (void|Promise<void>)}} props
 *   `courses` are `TrainingCourseDto`-shaped rows; `onCoursesChanged` refetches them.
 */
export default function CourseTable({ courses, onCoursesChanged }) {
  const [deactivating, setDeactivating] = useState(null);

  const handleActivate = async (course) => {
    try {
      await updateCourse(course.courseId, { isActive: true });
      await onCoursesChanged?.();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleConfirmDeactivate = async () => {
    try {
      await updateCourse(deactivating.courseId, { isActive: false });
      setDeactivating(null);
      await onCoursesChanged?.();
    } catch (error) {
      toast.error(error.message);
    }
  };

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Course</TableHead>
            <TableHead>Package</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Assigned</TableHead>
            <TableHead className="text-right">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {courses.map((course) => (
            <TableRow key={course.courseId}>
              <TableCell>
                <div className="font-medium">{course.name}</div>
                {course.description && (
                  <div className="text-xs text-muted-foreground">
                    {course.description}
                  </div>
                )}
              </TableCell>
              <TableCell>
                <PackageCell course={course} />
              </TableCell>
              <TableCell>
                <StatusBadge state={course.state} />
              </TableCell>
              <TableCell className="text-right">
                {course.assignedCount}
              </TableCell>
              <TableCell className="text-right">
                <RowActions
                  course={course}
                  onDeactivate={setDeactivating}
                  onActivate={handleActivate}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {deactivating && (
        <DeactivateDialog
          course={deactivating}
          open
          onOpenChange={(open) => !open && setDeactivating(null)}
          onConfirm={handleConfirmDeactivate}
        />
      )}
    </>
  );
}
