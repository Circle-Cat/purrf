import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { listCourses, openPreviewSession } from "@/api/trainingApi";
import useTrainingRuntime from "@/hooks/useTrainingRuntime";
import { Card } from "@/components/ui/card";

// There is no single-course GET; the admin catalogue itself only ever reads
// every row and picks the one it wants, so this page does the same.
const findCourseRow = (courses, courseId) =>
  courses.find((c) => String(c.courseId) === String(courseId)) ?? null;

/**
 * The page an administrator uses to see the package learners are on.
 *
 * It runs the same iframe, the same message bridge and the same origin check
 * the learner path uses, against the course's *live* package -- but with
 * `records: false`, because the session it opens names no assignment. Nothing
 * it observes is stored, and the server would refuse it if this page tried:
 * looking at what is live is not a run of it.
 *
 * That is also why there is no verdict bar and no CMI panel here. Those exist
 * on the trial page to decide whether a staged package may be published; a
 * preview decides nothing.
 *
 * @component
 */
export default function TrainingPreview() {
  const { courseId } = useParams();
  const { user } = useAuth() ?? {};
  const [course, setCourse] = useState(null);

  // Read the same way the trial page does: one fetch on mount, failure left
  // silent -- a course row that fails to load costs this page nothing but the
  // package name in the header line.
  useEffect(() => {
    let cancelled = false;
    setCourse(null);
    listCourses()
      .then(({ data }) => {
        if (!cancelled) setCourse(findCourseRow(data, courseId));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  const { session, loadError, frameRef, playerSrc } = useTrainingRuntime(
    courseId,
    user,
    { open: openPreviewSession, records: false },
  );

  return (
    <div className="space-y-5 p-6">
      <div>
        <h1 className="text-xl font-semibold">Preview</h1>
        <p className="mt-0.5 font-mono text-sm text-muted-foreground">
          {course?.name ? `${course.name} · ` : `Course #${courseId} · `}
          {course?.packageVersion
            ? `live package ${course.packageVersion}`
            : "the live package"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          Nothing here is recorded. This is the package learners are taking
          right now.
        </p>
      </div>

      <Card className="overflow-hidden py-0">
        {loadError ? (
          <p className="p-6 text-muted-foreground">{loadError}</p>
        ) : !session ? (
          <p className="p-6 text-muted-foreground">Opening the course...</p>
        ) : (
          <div className="flex aspect-video flex-col">
            <iframe
              ref={frameRef}
              title="Course"
              src={playerSrc}
              className="flex-1"
            />
          </div>
        )}
      </Card>
    </div>
  );
}
