import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { listEmails } from "@/api/emailApi";

/**
 * Load the caller's email addresses and sign-in identities for the
 * Sign in & security page.
 *
 * Exposes `refresh` so later mutating flows (add / make primary / remove /
 * unlink) can re-pull the view after they succeed.
 *
 * @returns {{
 *   isLoading: boolean,
 *   emails: Array<object>,
 *   internalIdentities: Array<object>,
 *   externalIdentities: Array<object>,
 *   refresh: () => Promise<void>,
 * }}
 */
export function useEmailSettings() {
  const [isLoading, setIsLoading] = useState(true);
  const [emails, setEmails] = useState([]);
  const [internalIdentities, setInternalIdentities] = useState([]);
  const [externalIdentities, setExternalIdentities] = useState([]);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await listEmails();
      setEmails(data?.emails ?? []);
      setInternalIdentities(data?.internalIdentities ?? []);
      setExternalIdentities(data?.externalIdentities ?? []);
    } catch (error) {
      toast.error(
        error?.response?.data?.message ||
          "Could not load your email settings. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return {
    isLoading,
    emails,
    internalIdentities,
    externalIdentities,
    refresh: load,
  };
}
