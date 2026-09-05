import { Fragment, useState } from "react";
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
import {
  assignBlockedReason,
  canAssign,
  liveStateLabel,
  publishBlockedReason,
} from "@/pages/AdminTraining/utils";
import {
  assignCourse,
  discardPackage,
  updateCourse,
  uploadPackage,
} from "@/api/trainingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { formatDateTimeWithZone, resolveViewerTimezone } from "@/utils/dateTime";
import AssignDialog from "@/pages/AdminTraining/components/AssignDialog";
import DeactivateDialog from "@/pages/AdminTraining/components/DeactivateDialog";
import UploadPackageDialog from "@/pages/AdminTraining/components/UploadPackageDialog";

// Only the two live states with a hosted package get a dot -- External link
// isn't ours to color, it just says where the course actually lives.
const LIVE_STATE_DOT_COLOR = {
  live: "var(--stage-hired)",
  no_package: "var(--stage-rejected)",
};

function StatusBadge({ liveState }) {
  const dotColor = LIVE_STATE_DOT_COLOR[liveState];
  return (
    <Badge variant="outline" className="gap-1.5">
      {dotColor && (
        <span
          aria-hidden="true"
          className="size-1.5 rounded-full"
          style={{ backgroundColor: dotColor }}
        />
      )}
      {liveStateLabel(liveState)}
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
// is the only place that rule is taught, so it isn't optional here, and it
// names which of the two rules is unmet rather than the commoner one.
function RowActions({ course, onDeactivate, onActivate, onUpload, onAssign }) {
  const toggle = (
    <ToggleActiveButton
      course={course}
      onDeactivate={onDeactivate}
      onActivate={onActivate}
    />
  );

  if (
    course.liveState === "no_package" ||
    course.liveState === "external_link"
  ) {
    return (
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="outline" onClick={() => onUpload(course)}>
          Upload package
        </Button>
        {toggle}
      </div>
    );
  }

  const assignable = canAssign(course);
  return (
    <div className="flex justify-end gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={!assignable}
        title={assignable ? undefined : assignBlockedReason(course)}
        onClick={() => onAssign(course)}
      >
        Assign
      </Button>
      <Button size="sm" variant="ghost" onClick={() => onUpload(course)}>
        Replace package
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

// The sub-row a staged package gets directly under the course it belongs to
// (spec §8). Spans every column rather than living in one of them, since it
// is describing the row above, not adding another cell to it.
function StagedRow({ course, onDiscard, onPublish }) {
  const { staged } = course;
  const verified = Boolean(staged.verifiedCompletableAt);
  const uploadedLabel = formatDateTimeWithZone(
    staged.uploadedAt,
    resolveViewerTimezone(),
  );

  return (
    <TableRow>
      <TableCell colSpan={5}>
        <div className="flex flex-col gap-1 rounded-md border bg-muted/40 p-3 text-sm">
          <div className="flex items-center justify-between gap-4">
            <span>
              {verified
                ? `✓ ${staged.packageVersion} staged — verified`
                : `⬆ ${staged.packageVersion} staged — not run yet`}
            </span>
            <span className="text-xs text-muted-foreground">
              {uploadedLabel}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {course.liveState === "live"
              ? `Learners still see ${course.packageVersion}.`
              : "Nothing is live yet; publishing makes this course assignable."}
          </p>
          <div className="flex justify-end gap-2 pt-1">
            <Button size="sm" variant="outline" asChild>
              <Link to={ROUTE_PATHS.TRAINING_TRIAL(course.courseId)}>
                Trial run
              </Link>
            </Button>
            <Button
              size="sm"
              disabled={!verified}
              title={publishBlockedReason(course)}
              onClick={() => onPublish(course)}
            >
              Publish
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onDiscard(course)}>
              Discard
            </Button>
          </div>
        </div>
      </TableCell>
    </TableRow>
  );
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
 * The staged sub-row's Publish button follows that same shape through
 * `setPublishing`, but its dialog does not exist yet -- a later task adds
 * the paired `publishing` state read and renders `<PublishDialog>` here,
 * the same way `deactivating` drives `DeactivateDialog` above.
 *
 * @param {{courses: Array<Object>, onCoursesChanged: () => (void|Promise<void>)}} props
 *   `courses` are `TrainingCourseDto`-shaped rows; `onCoursesChanged` refetches them.
 */
export default function CourseTable({ courses, onCoursesChanged }) {
  const [deactivating, setDeactivating] = useState(null);
  const [uploading, setUploading] = useState(null);
  const [assigning, setAssigning] = useState(null);
  // Named and shaped like the state above so a later task can attach
  // `<PublishDialog>` here without touching anything else in this file --
  // the read side is unused until that dialog exists, so it stays unnamed
  // here rather than tripping the unused-var lint rule.
  const [, setPublishing] = useState(null);

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

  // Refetch as soon as the upload lands, so the row's state and counts are
  // fresh while the dialog is still open showing the health box -- rejection
  // is left to the dialog itself, which renders the backend message inline.
  const handleConfirmUpload = async (file, onProgress) => {
    const { data } = await uploadPackage(uploading.courseId, file, onProgress);
    await onCoursesChanged?.();
    return data;
  };

  // Called by the dialog's onConfirm; closes the row and refetches once the
  // assignment lands.
  const handleConfirmAssign = async (payload) => {
    const result = await assignCourse(payload);
    setAssigning(null);
    await onCoursesChanged?.();
    return result;
  };

  // Drops the staged package without publishing it; the live package, if
  // any, is untouched. Same refetch-on-success rule as every mutation above.
  const handleDiscard = async (course) => {
    try {
      await discardPackage(course.courseId);
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
            <Fragment key={course.courseId}>
              <TableRow>
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
                  <StatusBadge liveState={course.liveState} />
                </TableCell>
                <TableCell className="text-right">
                  {course.assignedCount}
                </TableCell>
                <TableCell className="text-right">
                  <RowActions
                    course={course}
                    onDeactivate={setDeactivating}
                    onActivate={handleActivate}
                    onUpload={setUploading}
                    onAssign={setAssigning}
                  />
                </TableCell>
              </TableRow>
              {course.staged && (
                <StagedRow
                  course={course}
                  onDiscard={handleDiscard}
                  onPublish={setPublishing}
                />
              )}
            </Fragment>
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
      {uploading && (
        <UploadPackageDialog
          course={uploading}
          open
          onOpenChange={(open) => !open && setUploading(null)}
          onConfirm={handleConfirmUpload}
        />
      )}
      {assigning && (
        <AssignDialog
          course={assigning}
          open
          onOpenChange={(open) => !open && setAssigning(null)}
          onConfirm={handleConfirmAssign}
        />
      )}
    </>
  );
}
