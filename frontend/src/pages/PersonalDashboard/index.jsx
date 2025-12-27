import React from "react";

const PersonalDashboard = () => {
  return (
    <div className="personal-dashboard">
      <div className="flex items-start justify-between mb-5 shrink-0">
        <div className="flex items-center gap-2">
          <span role="img" aria-label="clapping hands" className="text-xl">
            &#x1F44F;
          </span>
          <h2 className="m-0 text-lg font-medium">Welcome</h2>
        </div>
      </div>
    </div>
  );
};

export default PersonalDashboard;
