import React from "react";
import "@/pages/Profile/components/TrainingSection.css";

import { Badge } from "@/components/ui/badge";
import {
  isIncompleteOnboarding,
  TrainingCategoryLabel,
} from "@/pages/Profile/utils";
import { formatInTz } from "@/utils/dateTime";

/**
 * Format an API timestamp (ISO 8601) as a calendar date in en-US,
 * interpreted in the viewer's profile timezone (an IANA string like
 * "Asia/Shanghai"). Falls back to UTC so the displayed date still
 * matches the stored value when the user has not picked a timezone.
 *
 * Returns "-" for null/empty/invalid inputs and for the 1970 sentinel
 * the backend stores when a training row hasn't been completed yet.
 */
const formatTrainingDate = (iso, timezone) => {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";
  if (date.getUTCFullYear() < 2000) return "-";
  return formatInTz(iso, timezone || "UTC", "MMM d, yyyy");
};

const TrainingSection = ({ list, timezone }) => {
  return (
    <div className="section">
      <div className="section-header">
        <h3>Training</h3>
      </div>

      {list && list.length > 0 ? (
        <table className="training-table">
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
              return (
                <tr
                  key={training.id}
                  className={required ? "training-row-required" : undefined}
                  data-testid={
                    required ? "training-row-required" : "training-row"
                  }
                >
                  <td>
                    {TrainingCategoryLabel[training.category] ??
                      training.category}
                  </td>
                  <td>
                    <Badge
                      className={
                        training.status === "done"
                          ? "training-status-completed"
                          : "training-status-not-completed"
                      }
                    >
                      {training.status === "done"
                        ? "Completed"
                        : "Not Completed"}
                    </Badge>
                  </td>
                  <td>
                    {formatTrainingDate(training.completedTimestamp, timezone)}
                  </td>
                  <td>{formatTrainingDate(training.deadline, timezone)}</td>
                  <td>
                    {training.link ? (
                      <a
                        href={training.link}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View Link
                      </a>
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
        <p className="section-text">No training records found.</p>
      )}
    </div>
  );
};

export default TrainingSection;
