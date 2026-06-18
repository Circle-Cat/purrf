import React from "react";

const LinkedInSection = ({ info }) => {
  return (
    <div className="section">
      <h3>LinkedIn link</h3>
      <div className="section-text">
        {info.linkedin ? (
          <a href={info.linkedin} target="_blank" rel="noopener noreferrer">
            {info.linkedin}
          </a>
        ) : (
          <p className="section-text">Not provided</p>
        )}
      </div>
    </div>
  );
};

export default LinkedInSection;
