import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

import { useEmailSettings } from "@/pages/SignInSecurity/hooks/useEmailSettings";
import EmailAddressList from "@/pages/SignInSecurity/components/EmailAddressList";
import SignInMethodList from "@/pages/SignInSecurity/components/SignInMethodList";

/**
 * Sign in & security settings page.
 *
 * Read-only comprehensive view of the caller's contact emails and linked
 * sign-in methods, backed by `GET /auth/emails`. Mutating actions (add email,
 * make primary, remove email, unlink identity) are layered on by later stories.
 * Cards span the full content area width.
 *
 * @component
 */
const SignInSecurity = () => {
  const { isLoading, emails, internalIdentity, externalIdentities } =
    useEmailSettings();

  return (
    <div className="flex flex-col gap-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle>Email addresses</CardTitle>
          <CardDescription>
            Your contact email addresses. Your primary address receives account
            notifications.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <EmailAddressList emails={emails} isLoading={isLoading} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sign-in methods</CardTitle>
          <CardDescription>
            The accounts you can use to sign in to Purrf.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SignInMethodList
            internalIdentity={internalIdentity}
            externalIdentities={externalIdentities}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>
    </div>
  );
};

export default SignInSecurity;
