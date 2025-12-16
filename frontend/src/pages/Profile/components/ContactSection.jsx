import React from "react";
import "@/pages/Profile/components/ContactSection.css";

const ContactSection = ({ info }) => {
  return (
    <>
      {/* LinkedIn */}
      <div className="section">
        <h3>LinkedIn link</h3>
        <p className="section-text">
          {info.linkedin ? (
            <a href={info.linkedin} target="_blank" rel="noopener noreferrer">
              {info.linkedin}
            </a>
          ) : (
            <span className="text-muted">Not provided</span>
          )}
        </p>
      </div>

      {/* Emails */}
      <div className="section">
        <h3>Email</h3>
        {info.emails &&
          info.emails.map((emailItem) => (
            <p key={emailItem.id} className="email-display-row section-text">
              {emailItem.email}
              {emailItem.isPrimary && (
                <span className="email-tag primary">Primary Email</span>
              )}
              {!emailItem.isPrimary && (
                <span className="email-tag alternative">Alternative Email</span>
              )}
            </p>
          ))}
      </div>
    </>
  );
};

export default ContactSection;
