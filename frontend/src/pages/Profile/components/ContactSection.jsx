import { Badge } from "@/components/ui/badge";
import React from "react";
import "@/pages/Profile/components/ContactSection.css";

const ContactSection = ({ info }) => {
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

      {/* Emails */}
      <div className="section">
        <h3>Email</h3>
        {info.emails &&
          info.emails.map((emailItem) => (
            <p key={emailItem.id} className="email-display-row section-text">
              {emailItem.email}
              {emailItem.isPrimary && (
                <Badge className="email-tag primary">Primary Email</Badge>
              )}
              {!emailItem.isPrimary && (
                <Badge className="email-tag alternative">
                  Alternative Email
                </Badge>
              )}
            </p>
          ))}
      </div>
    </>
  );
};

export default ContactSection;
