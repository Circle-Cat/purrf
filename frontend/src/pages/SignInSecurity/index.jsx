import { useState } from "react";
import { toast } from "sonner";

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardAction,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import {
  initiateSetPrimary,
  confirmSetPrimary,
  initiateUnlink,
  confirmUnlink,
} from "@/api/emailApi";
import { useEmailSettings } from "@/pages/SignInSecurity/hooks/useEmailSettings";
import { identityLabel } from "@/pages/SignInSecurity/providers";
import SignInMethodList from "@/pages/SignInSecurity/components/SignInMethodList";
import ContactEmailList from "@/pages/SignInSecurity/components/ContactEmailList";
import AddEmailDialog from "@/pages/SignInSecurity/components/AddEmailDialog";
import VerifyEmailDialog from "@/pages/SignInSecurity/components/VerifyEmailDialog";
import StepUpConfirmDialog from "@/pages/SignInSecurity/components/StepUpConfirmDialog";

const errorMessage = (error, fallback) =>
  error?.response?.data?.message || fallback;

/**
 * Sign in & security settings page.
 *
 * Two cards backed by `GET /auth/emails`. The sign-in methods card lists the
 * account's identities: set a method's email as the primary contact (step-up
 * OTP) or remove a method (step-up OTP, which also drops its synced contact
 * email). The emails card lists the account's contact addresses: add one
 * without verification (contact-only), and verify it (email OTP) to unlock it
 * as a sign-in method.
 *
 * @component
 */
const SignInSecurity = () => {
  const { isLoading, emails, internalIdentities, externalIdentities, refresh } =
    useEmailSettings();
  const [addOpen, setAddOpen] = useState(false);
  const [verifyTarget, setVerifyTarget] = useState(null);
  const [primaryTarget, setPrimaryTarget] = useState(null);
  const [unlinkTarget, setUnlinkTarget] = useState(null);

  const handleSetPrimary = async (email) => {
    try {
      const { data } = await initiateSetPrimary(email.emailId);
      setPrimaryTarget({
        emailId: email.emailId,
        email: email.email,
        state: data.state,
      });
    } catch (error) {
      toast.error(
        errorMessage(
          error,
          "Could not start setting your primary contact email.",
        ),
      );
    }
  };

  const handleConfirmSetPrimary = async (code) => {
    try {
      await confirmSetPrimary(primaryTarget.emailId, primaryTarget.state, code);
      setPrimaryTarget(null);
      toast.success("Primary contact email updated.");
      await refresh();
    } catch (error) {
      toast.error(
        errorMessage(error, "Could not set your primary contact email."),
      );
    }
  };

  const handleResendSetPrimary = async () => {
    const { data } = await initiateSetPrimary(primaryTarget.emailId);
    setPrimaryTarget((t) => ({ ...t, state: data.state }));
  };

  const handleUnlink = async (identity) => {
    try {
      const { data } = await initiateUnlink(identity.identityId);
      setUnlinkTarget({
        identityId: identity.identityId,
        label: identityLabel(identity),
        state: data.state,
      });
    } catch (error) {
      toast.error(
        errorMessage(error, "Could not start removing this sign-in method."),
      );
    }
  };

  const handleConfirmUnlink = async (code) => {
    try {
      await confirmUnlink(unlinkTarget.identityId, unlinkTarget.state, code);
      setUnlinkTarget(null);
      toast.success("Sign-in method removed.");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not remove this sign-in method."));
    }
  };

  const handleResendUnlink = async () => {
    const { data } = await initiateUnlink(unlinkTarget.identityId);
    setUnlinkTarget((t) => ({ ...t, state: data.state }));
  };

  return (
    <div className="flex flex-col gap-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle>Sign-in methods</CardTitle>
          <CardDescription>
            The methods you can use to sign in to Purrf. Your primary contact
            email receives account notifications.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SignInMethodList
            emails={emails}
            internalIdentities={internalIdentities}
            externalIdentities={externalIdentities}
            isLoading={isLoading}
            onUnlink={handleUnlink}
            onSetPrimary={handleSetPrimary}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Emails</CardTitle>
          <CardDescription>
            Email addresses on your account. An unverified address is
            contact-only — verify it to use it for signing in.
          </CardDescription>
          <CardAction>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setAddOpen(true)}
            >
              Add email
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <ContactEmailList
            emails={emails}
            isLoading={isLoading}
            onVerify={(emailRow) => setVerifyTarget(emailRow)}
          />
        </CardContent>
      </Card>

      <AddEmailDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onAdded={refresh}
      />

      <VerifyEmailDialog
        open={verifyTarget !== null}
        onOpenChange={(o) => {
          if (!o) setVerifyTarget(null);
        }}
        email={verifyTarget?.email ?? ""}
        onVerified={async () => {
          setVerifyTarget(null);
          await refresh();
        }}
      />

      <StepUpConfirmDialog
        open={primaryTarget !== null}
        onOpenChange={(o) => {
          if (!o) setPrimaryTarget(null);
        }}
        title="Set primary contact email"
        description={`Enter the 6-digit code we sent to your current primary contact email to make ${primaryTarget?.email} your primary contact email.`}
        confirmLabel="Set as primary"
        onConfirm={handleConfirmSetPrimary}
        onResend={handleResendSetPrimary}
      />

      <StepUpConfirmDialog
        open={unlinkTarget !== null}
        onOpenChange={(o) => {
          if (!o) setUnlinkTarget(null);
        }}
        title="Remove sign-in method"
        description={`Enter the 6-digit code we sent to your primary contact email to confirm removing ${unlinkTarget?.label}. Its contact email is removed too unless another sign-in method uses it.`}
        confirmLabel="Remove sign-in method"
        confirmVariant="destructive"
        onConfirm={handleConfirmUnlink}
        onResend={handleResendUnlink}
      />
    </div>
  );
};

export default SignInSecurity;
