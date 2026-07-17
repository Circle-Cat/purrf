import React from "react";
import { safeHttpUrl } from "@/utils/url";

const LinkedInSection = ({ info }) => {
  const safeUrl = safeHttpUrl(info.linkedin);

  return (
    <div className="section">
      <h3>LinkedIn link</h3>
      <div className="section-text">
        {safeUrl ? (
          <a href={safeUrl} target="_blank" rel="noopener noreferrer">
            {info.linkedin}
          </a>
        ) : info.linkedin ? (
          <span className="section-text">{info.linkedin}</span>
        ) : (
          <p className="section-text">Not provided</p>
        )}
      </div>
    </div>
  );
};

export default LinkedInSection;
