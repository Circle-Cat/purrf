import React from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const EmailSection = ({ info }) => {
  const primaryEmail = info.emails?.find((emailItem) => emailItem.isPrimary);

  return (
    <div className="section">
      <div className="section-header">
        <h3>Contact Email</h3>
        <Button size="sm" asChild>
          <Link to={ROUTE_PATHS.SIGN_IN_SECURITY}>
            Manage in Settings
            <ExternalLink size={14} />
          </Link>
        </Button>
      </div>
      {primaryEmail ? (
        <p className="section-text">{primaryEmail.email}</p>
      ) : (
        <p className="section-text">Not provided</p>
      )}
    </div>
  );
};

export default EmailSection;
