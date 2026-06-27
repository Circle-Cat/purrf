import { ENV_LABELS } from "@/utils/deployEnv";
import { cn } from "@/lib/utils";

const VARIANT_CLASSES = {
  staging: "bg-amber-500 text-gray-800",
  test: "bg-indigo-600 text-white",
};

const EnvironmentBanner = ({ env }) => {
  const label = ENV_LABELS[env];
  if (!label) {
    return null;
  }
  return (
    <div
      className={cn(
        "fixed inset-x-0 top-16 z-[99] flex h-10 items-center justify-center text-sm font-bold uppercase tracking-[0.12em] shadow-[0_1px_3px_rgba(0,0,0,0.15)]",
        VARIANT_CLASSES[env],
      )}
      role="status"
      aria-label={label}
      data-variant={env}
      data-testid="env-banner"
    >
      {label}
    </div>
  );
};

export default EnvironmentBanner;
