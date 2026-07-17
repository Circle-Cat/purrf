import { useNavigate } from "react-router-dom";

import { useAuth } from "@/context/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { performGlobalLogout } from "@/utils/auth";
import OtpVerifyForm from "@/components/common/OtpVerifyForm";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

/**
 * Whether an address is a Circle Cat Google Workspace mailbox
 * (@circlecat.org). Deliberately narrower than the backend's
 * is_company_email: @u.circlecat.org (Microsoft) is excluded because the
 * wall hint below names Google Workspace specifically. Display-only
 * signal; the backend stays authoritative.
 *
 * @param {string | undefined} email - Address to test.
 * @returns {boolean} True for a Google Workspace company address.
 */
const isWorkspaceEmail = (email) => /@circlecat\.org$/i.test(email || "");

/**
 * Full-screen hard wall: a user with no confirmed contact email must
 * verify one here before reaching any other page. Reachable only via the
 * HardWallGate; offers a logout escape hatch so a user with an unreachable
 * address is never trapped.
 *
 * Internal-employee variant: when the sign-in claim is a Google Workspace
 * company address (legacy LDAP staff first logging into the new system),
 * the copy instead asks them to verify their @circlecat.org email and to
 * contact their manager if that mailbox cannot receive the code. Hint
 * only — nothing is enforced.
 *
 * Needs-link variant: when the sign-in's email already belongs to an existing
 * account (`needsLink`), the same OTP proves the mailbox and links this
 * sign-in method into that account instead — the address is locked to the
 * sign-in's own email, since verifying any other address cannot resolve the
 * collision.
 */
const VerifyRequired = () => {
  const { user, needsLink, refreshAuth } = useAuth();
  const navigate = useNavigate();
  const isInternal = !needsLink && isWorkspaceEmail(user?.email);

  const handleVerified = async () => {
    await refreshAuth();
    navigate(ROUTE_PATHS.PROFILE, { replace: true });
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            {needsLink
              ? "Link this sign-in to your account"
              : "Verify your email to continue"}
          </CardTitle>
          <CardDescription>
            {needsLink
              ? "An account already exists for this email. Verify it once and " +
                "this sign-in method will be linked to that account."
              : isInternal
                ? "As a Circle Cat member, please verify your Google Workspace " +
                  "email (@circlecat.org) as your contact address. If this " +
                  "address can't receive the verification code, please contact " +
                  "your manager."
                : "We need a confirmed contact email to deliver application " +
                  "updates and round notifications."}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <OtpVerifyForm
            initialEmail={user?.email || ""}
            onVerified={handleVerified}
            idPrefix="verify"
            lockEmail={needsLink}
          />
        </CardContent>

        <CardFooter className="justify-end">
          <Button variant="ghost" onClick={performGlobalLogout}>
            Log out
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
};

export default VerifyRequired;
