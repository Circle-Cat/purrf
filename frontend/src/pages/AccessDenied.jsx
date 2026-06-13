const AccessDenied = ({ message }) => {
  return (
    <div className="access-denied-page">
      <h1>403 Forbidden</h1>
      <p>{message || "You do not have permission to access this site."}</p>
    </div>
  );
};

export default AccessDenied;
