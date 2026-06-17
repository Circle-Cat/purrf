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
 */
const VerifyRequired = () => {
  const { user, refreshAuth } = useAuth();
  const navigate = useNavigate();

  const handleVerified = async () => {
    await refreshAuth();
    navigate(ROUTE_PATHS.PROFILE, { replace: true });
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Verify your email to continue</CardTitle>
          <CardDescription>
            We need a confirmed contact email to deliver application updates and
            round notifications.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <OtpVerifyForm
            initialEmail={user?.email || ""}
            onVerified={handleVerified}
            idPrefix="verify"
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
