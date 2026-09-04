import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listCourses } from "@/api/trainingApi";
import CourseTable from "@/pages/AdminTraining/components/CourseTable";

/**
 * The admin landing page for training: every course, and whether it can be
 * assigned yet. `null` courses means still loading, `[]` means the
 * catalogue is genuinely empty -- the two need different copy.
 */
export default function AdminTraining() {
  const [courses, setCourses] = useState(null);

  // The single source of truth for the list. Row actions in CourseTable
  // never patch `courses` themselves -- they call this again once their
  // mutation succeeds, so the counts shown always come from the server.
  const fetchCourses = useCallback(
    () =>
      listCourses()
        .then(({ data }) => setCourses(data ?? []))
        .catch((error) => toast.error(error.message)),
    [],
  );

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold">Training courses</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            A course cannot be assigned until someone has run it to completion.
          </CardTitle>
        </CardHeader>
        <CardContent>
          {courses === null ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : courses.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No training courses yet.
            </p>
          ) : (
            <CourseTable courses={courses} onCoursesChanged={fetchCourses} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
