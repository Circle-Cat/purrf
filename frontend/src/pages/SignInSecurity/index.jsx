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
  removeContactEmail,
} from "@/api/emailApi";
import { useEmailSettings } from "@/pages/SignInSecurity/hooks/useEmailSettings";
import { identityLabel } from "@/pages/SignInSecurity/providers";
import SignInMethodList from "@/pages/SignInSecurity/components/SignInMethodList";
import AddEmailDialog from "@/pages/SignInSecurity/components/AddEmailDialog";
import VerifyEmailDialog from "@/pages/SignInSecurity/components/VerifyEmailDialog";
import StepUpConfirmDialog from "@/pages/SignInSecurity/components/StepUpConfirmDialog";

const errorMessage = (error, fallback) =>
  error?.response?.data?.message || fallback;

/**
 * Sign in & security settings page.
 *
 * A single card backed by `GET /auth/emails`, listing the account's sign-in
 * methods and its contact emails together: set a method's email as the
 * primary contact (step-up OTP), remove a method (step-up OTP; its email
 * address stays on the account as a contact-only row), add a backup email
 * with immediate verification (email OTP in the dialog), verify a legacy
 * unverified address (email OTP) to unlock it as a sign-in method, and
 * remove a non-primary contact email (no OTP for a legacy unverified row;
 * the server refuses to remove the address behind the caller's own current
 * passwordless session).
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

  // Step-up codes go to the current primary; name the actual address in the
  // dialogs so the user knows which inbox to check.
  const primaryEmail =
    emails.find((email) => email.isPrimary)?.email ??
    "your primary contact email";

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

  const handleRemoveEmail = async (emailRow) => {
    try {
      await removeContactEmail(emailRow.emailId);
      toast.success("Email removed.");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not remove this email."));
    }
  };

  return (
    <div className="flex flex-col gap-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle>Sign-in methods & emails</CardTitle>
          <CardDescription>
            The methods you can use to sign in to Purrf. Your primary contact
            email receives account notifications; an unverified email is
            contact-only until you verify it.
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
          <SignInMethodList
            emails={emails}
            internalIdentities={internalIdentities}
            externalIdentities={externalIdentities}
            isLoading={isLoading}
            onUnlink={handleUnlink}
            onSetPrimary={handleSetPrimary}
            onVerify={(emailRow) => setVerifyTarget(emailRow)}
            onRemove={handleRemoveEmail}
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
        description={`Enter the 6-digit code we sent to ${primaryEmail} to make ${primaryTarget?.email} your primary contact email.`}
        confirmLabel="Set as primary"
        otpEmail={primaryEmail}
        onConfirm={handleConfirmSetPrimary}
        onResend={handleResendSetPrimary}
      />

      <StepUpConfirmDialog
        open={unlinkTarget !== null}
        onOpenChange={(o) => {
          if (!o) setUnlinkTarget(null);
        }}
        title="Remove sign-in method"
        description={`Enter the 6-digit code we sent to ${primaryEmail} to confirm removing ${unlinkTarget?.label}. This removes only the sign-in method — its email address stays on your account.`}
        confirmLabel="Remove sign-in method"
        confirmVariant="destructive"
        otpEmail={primaryEmail}
        onConfirm={handleConfirmUnlink}
        onResend={handleResendUnlink}
      />
    </div>
  );
};

export default SignInSecurity;
