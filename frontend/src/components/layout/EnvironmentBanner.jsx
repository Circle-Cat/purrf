import "./EnvironmentBanner.css";
import { ENV_LABELS } from "@/utils/deployEnv";

const EnvironmentBanner = ({ env }) => {
  const label = ENV_LABELS[env];
  if (!label) {
    return null;
  }
  return (
    <div
      className={`env-banner env-banner--${env}`}
      role="status"
      aria-label={label}
      data-testid="env-banner"
    >
      {label}
    </div>
  );
};

export default EnvironmentBanner;
