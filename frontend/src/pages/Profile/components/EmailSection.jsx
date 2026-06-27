import React from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const EmailSection = ({ info }) => {
  const primaryEmail = info.emails?.find((emailItem) => emailItem.isPrimary);

  return (
    <div className="mb-12">
      <div className="mb-5 flex items-center justify-between">
        <h3 className="mb-5 mt-0 text-xl font-semibold tracking-[-0.015em] text-foreground">
          Contact Email
        </h3>
        <Button size="sm" asChild>
          <Link to={ROUTE_PATHS.SIGN_IN_SECURITY}>
            Manage in Settings
            <ExternalLink size={14} />
          </Link>
        </Button>
      </div>
      {primaryEmail ? (
        <p className="mb-3 text-base leading-relaxed text-foreground">
          {primaryEmail.email}
        </p>
      ) : (
        <p className="mb-3 text-base leading-relaxed text-foreground">
          Not provided
        </p>
      )}
    </div>
  );
};

export default EmailSection;
