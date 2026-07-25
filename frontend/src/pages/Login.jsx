import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { devLogin, fetchAuthConfig, fetchMe, googleLoginUrl } from "../api";

export default function Login({ onLogin, initialError = "" }) {
  const [config, setConfig] = useState({
    google_enabled: false,
    dev_login_enabled: true,
  });
  const [error, setError] = useState(initialError);

  useEffect(() => {
    fetchAuthConfig()
      .then(setConfig)
      .catch(() => {});
  }, []);

  return (
    <div className="center">
      <div className="card login-card">
        <h1>🔒 Knowledge Base</h1>
        <p className="muted">
          Sign in to ask questions about your company's documents. You'll only
          ever see answers your role is allowed to access.
        </p>

        {error && <div className="error">{error}</div>}

        {config.google_enabled && (
          <a className="google-btn" href={googleLoginUrl()}>
            <span className="g">G</span> Sign in with Google
          </a>
        )}

        {config.google_enabled && config.dev_login_enabled && (
          <div className="divider">
            <span>or dev login</span>
          </div>
        )}

        {config.dev_login_enabled && (
          <DevLoginForm onLogin={onLogin} onError={setError} />
        )}

        {!config.dev_login_enabled && !config.google_enabled && (
          <div className="error">
            No login method is configured. Set GOOGLE_CLIENT_ID/SECRET or enable
            DEV_AUTH_ENABLED.
          </div>
        )}
      </div>
    </div>
  );
}

// Dev login: pick an email + roles to test the ACL model without Google OAuth.
function DevLoginForm({ onLogin, onError }) {
  const [email, setEmail] = useState("alice@example.com");
  const [name, setName] = useState("Alice");
  const [roles, setRoles] = useState("hr");
  const [isAdmin, setIsAdmin] = useState(true);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    onError("");
    try {
      await devLogin({
        email,
        name,
        roles: roles
          .split(",")
          .map((r) => r.trim())
          .filter(Boolean),
        is_admin: isAdmin,
      });
      const me = await fetchMe();
      onLogin(me);
      navigate("/");
    } catch (err) {
      onError(err?.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>Email</label>
      <input value={email} onChange={(e) => setEmail(e.target.value)} required />

      <label>Name</label>
      <input value={name} onChange={(e) => setName(e.target.value)} />

      <label>Roles (comma-separated, blank = customer)</label>
      <input
        value={roles}
        onChange={(e) => setRoles(e.target.value)}
        placeholder="hr, finance"
      />

      <label className="checkbox">
        <input
          type="checkbox"
          checked={isAdmin}
          onChange={(e) => setIsAdmin(e.target.checked)}
        />
        Admin (can upload &amp; manage documents/users)
      </label>

      <button className="btn-primary" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
