import React from "react";
import { formatTimeDuration } from "@/pages/Profile/utils";

const ExperienceSection = ({ list, onEditClick }) => {
  return (
    <div className="section">
      <div className="section-header">
        <h3>Experience</h3>
        <button
          className="edit-button"
          aria-label="Edit Experience"
          onClick={onEditClick}
        >
          +
        </button>
      </div>

      {list && list.length > 0 ? (
        <div className="experience-list">
          {list.map((exp) => (
            <div key={exp.id} className="experience-list-item">
              <h6>{exp.title}</h6>
              <p>{exp.company}</p>
              <p className="duration-text">
                {formatTimeDuration(
                  exp.startMonth,
                  exp.startYear,
                  exp.endMonth,
                  exp.endYear,
                  exp.isCurrentlyWorking,
                )}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="section-text">No experience added.</p>
      )}
    </div>
  );
};

export default ExperienceSection;
