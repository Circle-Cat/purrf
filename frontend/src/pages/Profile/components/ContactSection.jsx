import React from "react";
import { Link } from "react-router-dom";

import { ROUTE_PATHS } from "@/constants/RoutePaths";
import "@/pages/Profile/components/ContactSection.css";

const ContactSection = ({ info }) => {
  const primaryEmail = info.emails?.find((emailItem) => emailItem.isPrimary);

  return (
    <>
      {/* LinkedIn */}
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

      {/* Email — only the primary contact email, managed in Settings. */}
      <div className="section">
        <h3>Email</h3>
        {primaryEmail ? (
          <p className="email-display-row section-text">{primaryEmail.email}</p>
        ) : (
          <p className="section-text">Not provided</p>
        )}
        <Link to={ROUTE_PATHS.SIGN_IN_SECURITY} className="manage-email-link">
          Manage in Settings
        </Link>
      </div>
    </>
  );
};

export default ContactSection;
