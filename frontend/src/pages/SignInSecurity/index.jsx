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
import SignInMethodList from "@/pages/SignInSecurity/components/SignInMethodList";
import AddSignInMethodDialog from "@/pages/SignInSecurity/components/AddSignInMethodDialog";
import StepUpConfirmDialog from "@/pages/SignInSecurity/components/StepUpConfirmDialog";

const errorMessage = (error, fallback) =>
  error?.response?.data?.message || fallback;

const PROVIDER_LABELS = {
  "google-oauth2": "Google",
  google: "Google",
  email: "Email",
  auth0: "Email & password",
};

const identityLabel = (identity) => {
  const provider = (identity.subjectIdentifier || "").split("|")[0];
  const name = PROVIDER_LABELS[provider] || provider || "this sign-in method";
  return identity.emailClaim ? `${name} (${identity.emailClaim})` : name;
};

/**
 * Sign in & security settings page.
 *
 * Sign-in methods are the management subject; each method's email is a contact
 * address synced from it, and the primary one receives notifications. Backed by
 * `GET /auth/emails`: add a sign-in method (email OTP), set a method's email as
 * the primary contact (step-up OTP), and unlink a sign-in method (step-up OTP,
 * which also drops its synced contact email). A single full-width card.
 *
 * @component
 */
const SignInSecurity = () => {
  const { isLoading, emails, internalIdentities, externalIdentities, refresh } =
    useEmailSettings();
  const [addOpen, setAddOpen] = useState(false);
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
        errorMessage(error, "Could not start switching your primary email."),
      );
    }
  };

  const handleConfirmSetPrimary = async (code) => {
    try {
      await confirmSetPrimary(primaryTarget.emailId, primaryTarget.state, code);
      setPrimaryTarget(null);
      toast.success("Primary email updated.");
      await refresh();
    } catch (error) {
      toast.error(errorMessage(error, "Could not switch your primary email."));
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
            The accounts you can use to sign in to Purrf. Each method&apos;s
            email is a contact address; your primary one receives account
            notifications.
          </CardDescription>
          <CardAction>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setAddOpen(true)}
            >
              Add sign-in method
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
          />
        </CardContent>
      </Card>

      <AddSignInMethodDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onAdded={refresh}
      />

      <StepUpConfirmDialog
        open={primaryTarget !== null}
        onOpenChange={(o) => {
          if (!o) setPrimaryTarget(null);
        }}
        title="Switch primary email"
        description={`Enter the 6-digit code we sent to your current primary email to make ${primaryTarget?.email} your primary contact address.`}
        confirmLabel="Switch primary"
        onConfirm={handleConfirmSetPrimary}
        onResend={handleResendSetPrimary}
      />

      <StepUpConfirmDialog
        open={unlinkTarget !== null}
        onOpenChange={(o) => {
          if (!o) setUnlinkTarget(null);
        }}
        title="Remove sign-in method"
        description={`Enter the 6-digit code we sent to your primary email to confirm removing ${unlinkTarget?.label}. Its contact email is removed too unless another sign-in method uses it.`}
        confirmLabel="Remove sign-in method"
        confirmVariant="destructive"
        onConfirm={handleConfirmUnlink}
        onResend={handleResendUnlink}
      />
    </div>
  );
};

export default SignInSecurity;
