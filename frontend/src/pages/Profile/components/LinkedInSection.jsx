import React from "react";
import { safeHttpUrl } from "@/utils/url";

const LinkedInSection = ({ info }) => {
  const safeUrl = safeHttpUrl(info.linkedin);

  const sectionText = "mb-3 text-base leading-relaxed text-foreground";

  return (
    <div className="mb-12">
      <h3 className="mb-5 mt-0 text-xl font-semibold tracking-[-0.015em] text-foreground">
        LinkedIn link
      </h3>
      <div className={sectionText}>
        {safeUrl ? (
          <a
            href={safeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary no-underline hover:underline"
          >
            {info.linkedin}
          </a>
        ) : info.linkedin ? (
          <span className={sectionText}>{info.linkedin}</span>
        ) : (
          <p className={sectionText}>Not provided</p>
        )}
      </div>
    </div>
  );
};

export default LinkedInSection;
