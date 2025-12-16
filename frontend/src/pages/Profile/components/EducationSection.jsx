import React from "react";
import { formatTimeDuration } from "@/pages/Profile/utils";

const EducationSection = ({ list, onEditClick }) => {
  return (
    <div className="section">
      <div className="section-header">
        <h3>Education</h3>
        <button
          className="edit-button"
          aria-label="Edit Education"
          onClick={onEditClick}
        >
          +
        </button>
      </div>

      {list.length > 0 ? (
        <div className="education-list">
          {list.map((edu) => (
            <div key={edu.id} className="education-list-item">
              <h6>{edu.institution}</h6>
              <p>
                {edu.degree}'s degree, {edu.field}
              </p>
              <p className="duration-text">
                {formatTimeDuration(
                  edu.startMonth,
                  edu.startYear,
                  edu.endMonth,
                  edu.endYear,
                )}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="section-text">No education added.</p>
      )}
    </div>
  );
};

export default EducationSection;
