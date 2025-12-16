import React from "react";
import "@/pages/Profile/components/TrainingSection.css";

import { formatDateFromParts } from "@/pages/Profile/utils";

const TrainingSection = ({ list }) => {
  const formatDisplay = (m, y) => {
    const dateStr = formatDateFromParts(m, y);
    if (!dateStr) return "-";
    return `${m.substring(0, 3)} ${y}`;
  };

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
            {list.map((training) => (
              <tr key={training.id}>
                <td>{training.name}</td>
                <td>
                  <span
                    className={`training-tag ${training.status.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                  >
                    {training.status === "done" ? "Completed" : "Not Completed"}
                  </span>
                </td>
                <td>
                  {formatDisplay(
                    training.completionMonth,
                    training.completionYear,
                  )}
                </td>
                <td>{formatDisplay(training.dueMonth, training.dueYear)}</td>
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
            ))}
          </tbody>
        </table>
      ) : (
        <p className="section-text">No training records found.</p>
      )}
    </div>
  );
};

export default TrainingSection;
