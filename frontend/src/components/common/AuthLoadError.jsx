import { performGlobalLogout } from "@/utils/auth";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

/**
 * Full-screen fallback shown when the app could not determine the user's auth
 * state. Covers two distinct cases:
 * - Connectivity: `/permissions/me` failed with a 401 (expired session), a
 *   network error, a timeout, or a 5xx. A load failure must never be mistaken
 *   for an unverified user, or the user gets trapped at the verify wall with
 *   no working path back to sign-in.
 * - Refusal: the backend responded 400, actively refusing the login (e.g. an
 *   unlisted connection) with an actionable message. Retrying can never
 *   succeed here, so no Retry button is shown — only the exact server message
 *   and a way to log in again.
 *
 * @component
 * @param {Object} props
 * @param {boolean} [props.sessionExpired=false] - True when the failure was a
 *   401, so the copy asks the user to sign in again rather than retry.
 * @param {string | null} [props.refusalMessage=null] - The server's refusal
 *   reason from a 400 response. When set, takes precedence over
 *   `sessionExpired`/the default connectivity copy, is shown verbatim, and
 *   hides the Retry button.
 * @param {() => void} [props.onRetry] - Re-pulls auth state (used for transient
 *   failures); typically `refreshAuth` from the auth context.
 */
const AuthLoadError = ({
  sessionExpired = false,
  refusalMessage = null,
  onRetry,
}) => {
  const isRefusal = Boolean(refusalMessage);

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            {isRefusal
              ? "Sign-in was refused"
              : sessionExpired
                ? "Your session has expired"
                : "Couldn't load your account"}
          </CardTitle>
          <CardDescription>
            {isRefusal
              ? refusalMessage
              : sessionExpired
                ? "Please log in again to continue."
                : "We couldn't reach the server to load your account. Check your connection and try again."}
          </CardDescription>
        </CardHeader>

        <CardContent className="flex justify-end gap-3">
          {!sessionExpired && !isRefusal && (
            <Button variant="outline" onClick={onRetry}>
              Retry
            </Button>
          )}
          <Button onClick={performGlobalLogout}>Log in again</Button>
        </CardContent>
      </Card>
    </div>
  );
};

export default AuthLoadError;
