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
  liveStateLabel,
  publishBlockedReason,
} from "@/pages/AdminTraining/utils";
import {
  discardPackage,
  publishPackage,
  updateCourse,
  uploadPackage,
} from "@/api/trainingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import {
  formatDateTimeWithZone,
  resolveViewerTimezone,
} from "@/utils/dateTime";
import DeactivateDialog from "@/pages/AdminTraining/components/DeactivateDialog";
import PublishDialog from "@/pages/AdminTraining/components/PublishDialog";
import UploadPackageDialog from "@/pages/AdminTraining/components/UploadPackageDialog";

// Only the two live states with a hosted course get a dot -- External link
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
function RowActions({ course, onDeactivate, onActivate, onUpload }) {
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

  return (
    <div className="flex justify-end gap-2">
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
    // The version is the natural thing to click when the question is "what
    // exactly are learners on right now" -- so it is the door to the answer
    // rather than a separate button competing with the row's own actions.
    return (
      <Link
        to={ROUTE_PATHS.TRAINING_PREVIEW(course.courseId)}
        className="font-mono text-xs text-primary underline-offset-4 hover:underline"
      >
        {course.packageVersion}
      </Link>
    );
  }
  return <span className="text-muted-foreground">—</span>;
}

// The sub-row a staged package gets directly under the course it belongs to
// (spec §8). Spans every column rather than living in one of them, since it
// is describing the row above, not adding another cell to it.
function StagedRow({ course, onDiscard, onPublish, discarding }) {
  const { staged } = course;
  const verified = Boolean(staged.verifiedCompletableAt);
  const uploadedLabel = formatDateTimeWithZone(
    staged.uploadedAt,
    resolveViewerTimezone(),
  );
  // A package built by a toolchain we cannot read (Captivate, iSpring, a
  // bare Storyline export) carries no version at all -- same class of
  // package PackageHealthBox already warns about. Name the thing without a
  // version rather than leave a gap in the sentence, matching how
  // UploadPackageDialog picks between "package {version}" and "the current
  // package" on this same nullability.
  const stagedName = staged.packageVersion
    ? `${staged.packageVersion} staged`
    : "the staged package";

  return (
    <TableRow>
      <TableCell colSpan={5}>
        <div className="flex flex-col gap-1 rounded-md border bg-muted/40 p-3 text-sm">
          <div className="flex items-center justify-between gap-4">
            <span>
              {verified
                ? `✓ ${stagedName} — verified`
                : `⬆ ${stagedName} — not run yet`}
            </span>
            <span className="text-xs text-muted-foreground">
              {uploadedLabel}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {course.liveState === "live"
              ? course.packageVersion
                ? `Learners still see ${course.packageVersion}.`
                : "Learners still see the current package."
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
            <Button
              size="sm"
              variant="ghost"
              disabled={discarding}
              onClick={() => onDiscard(course)}
            >
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
 * `publishing` / `setPublishing`, driving `<PublishDialog>` the same way
 * `deactivating` drives `DeactivateDialog` above.
 *
 * @param {{courses: Array<Object>, onCoursesChanged: () => (void|Promise<void>)}} props
 *   `courses` are `TrainingCourseDto`-shaped rows; `onCoursesChanged` refetches them.
 */
export default function CourseTable({ courses, onCoursesChanged }) {
  const [deactivating, setDeactivating] = useState(null);
  const [uploading, setUploading] = useState(null);
  const [publishing, setPublishing] = useState(null);
  // Which course's Discard is waiting on its DELETE. Discard has no dialog to
  // hold a busy flag for it, so the row holds one: a second click while the
  // first is in flight deletes nothing and comes back as a red toast on an
  // action that worked.
  const [discarding, setDiscarding] = useState(null);

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

  // Drops the staged package without publishing it; the live package, if
  // any, is untouched. Same refetch-on-success rule as every mutation above.
  const handleDiscard = async (course) => {
    setDiscarding(course.courseId);
    try {
      await discardPackage(course.courseId);
      await onCoursesChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setDiscarding(null);
    }
  };

  // Moves the staged package into the live slot; the dialog already told
  // the admin what that costs. Same refetch-on-success rule as every
  // mutation above -- counts like `assignedCount` only the server knows.
  const handleConfirmPublish = async () => {
    try {
      await publishPackage(publishing.courseId);
      setPublishing(null);
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
                  />
                </TableCell>
              </TableRow>
              {course.staged && (
                <StagedRow
                  course={course}
                  onDiscard={handleDiscard}
                  onPublish={setPublishing}
                  discarding={discarding === course.courseId}
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
      {publishing && (
        <PublishDialog
          course={publishing}
          open
          onOpenChange={(open) => !open && setPublishing(null)}
          onConfirm={handleConfirmPublish}
        />
      )}
    </>
  );
}
