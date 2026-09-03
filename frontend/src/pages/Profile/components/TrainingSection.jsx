import React from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { TrainingCategoryLabel } from "@/pages/Profile/utils";
import { formatInTz } from "@/utils/dateTime";
import { isIncompleteOnboarding } from "@/utils/training";
import { safeHttpUrl } from "@/utils/url";

/**
 * Format an API timestamp (ISO 8601) as a calendar date in en-US,
 * interpreted in the viewer's profile timezone (an IANA string like
 * "Asia/Shanghai").
 *
 * Returns "-" for null/empty/invalid inputs and for the 1970 sentinel
 * the backend stores when a training row hasn't been completed yet.
 */
const formatTrainingDate = (iso, timezone) => {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";
  if (date.getUTCFullYear() < 2000) return "-";
  return formatInTz(iso, timezone, "MMM d, yyyy");
};

// Three states, not two: a learner partway through a course must be able to
// see that they are partway through it, now that the shim actually writes
// "in_progress".
const STATUS_BADGE = {
  to_do: {
    label: "Not Started",
    className: "bg-primary text-primary-foreground",
  },
  in_progress: {
    label: "In Progress",
    className: "bg-secondary text-secondary-foreground",
  },
  done: { label: "Completed", className: "bg-accent text-primary" },
};

// Opening an in-app course is named after where the learner is, not what
// they'd be doing. A finished course is always "Review", never "Retake":
// reopening it must not read as a way back out of Done.
const IN_APP_ACTION_LABEL = {
  to_do: "Start",
  in_progress: "Continue",
  done: "Review",
};

const TrainingSection = ({ list, timezone }) => {
  return (
    <div className="mb-12">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h3 className="mb-1 mt-0 text-xl font-semibold tracking-[-0.015em] text-foreground">
            Training
          </h3>
          {list && list.length > 0 && (
            <p className="text-sm text-muted-foreground">
              Dates shown in {timezone}.
            </p>
          )}
        </div>
      </div>

      {list && list.length > 0 ? (
        <table className="mt-5 w-full border-separate border-spacing-0 overflow-hidden rounded-xl border text-[0.9375rem] text-foreground [&_a:hover]:underline [&_a]:font-medium [&_a]:text-primary [&_a]:no-underline [&_td]:border-b [&_td]:px-5 [&_td]:py-4 [&_td]:text-left [&_th]:border-b [&_th]:bg-muted [&_th]:px-5 [&_th]:py-4 [&_th]:text-left [&_th]:text-sm [&_th]:font-semibold [&_th]:uppercase [&_th]:tracking-[0.05em] [&_th]:text-foreground">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Completed On</th>
              <th>Due Date</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {list.map((training) => {
              const required = isIncompleteOnboarding(training);
              const safeLink = safeHttpUrl(training.link);
              const statusBadge =
                STATUS_BADGE[training.status] ?? STATUS_BADGE.to_do;
              const actionLabel =
                IN_APP_ACTION_LABEL[training.status] ??
                IN_APP_ACTION_LABEL.to_do;
              return (
                <tr
                  key={training.id}
                  className={
                    required
                      ? "bg-accent transition-colors hover:bg-[#D6CCFB] [&:last-child>td]:border-b-0"
                      : "bg-white transition-colors hover:bg-muted [&:last-child>td]:border-b-0"
                  }
                  data-testid={
                    required ? "training-row-required" : "training-row"
                  }
                >
                  <td>
                    {training.name ??
                      TrainingCategoryLabel[training.category] ??
                      training.category}
                  </td>
                  <td>
                    <Badge className={statusBadge.className}>
                      {statusBadge.label}
                    </Badge>
                  </td>
                  <td>
                    {formatTrainingDate(training.completedTimestamp, timezone)}
                  </td>
                  <td>{formatTrainingDate(training.deadline, timezone)}</td>
                  <td>
                    {safeLink ? (
                      <a
                        href={safeLink}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View Link
                      </a>
                    ) : training.courseId ? (
                      <Link to={ROUTE_PATHS.TRAINING_COURSE(training.id)}>
                        {actionLabel}
                      </Link>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="mb-3 text-base leading-relaxed text-foreground">
          No training records found.
        </p>
      )}
    </div>
  );
};

export default TrainingSection;
