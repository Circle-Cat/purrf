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
 * Full-screen hard wall: a user with no confirmed contact email must
 * verify one here before reaching any other page. Reachable only via the
 * HardWallGate; offers a logout escape hatch so a user with an unreachable
 * address is never trapped.
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
