import { useEffect, useState } from "react";
import { Navigate, Link, Route, Routes, useNavigate } from "react-router-dom";
import { clearToken, consumeAuthHash, fetchMe, getToken } from "./api";
import Login from "./pages/Login.jsx";
import Chat from "./pages/Chat.jsx";
import Admin from "./pages/Admin.jsx";

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    // If we just came back from Google OAuth, grab the token from the URL hash.
    const err = consumeAuthHash();
    if (err) setAuthError("Google sign-in failed. Please try again.");

    if (!getToken()) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="center muted">Loading…</div>;

  return (
    <div className="app">
      {user && <NavBar user={user} onLogout={() => setUser(null)} />}
      <Routes>
        <Route
          path="/login"
          element={
            user ? (
              <Navigate to="/" />
            ) : (
              <Login onLogin={setUser} initialError={authError} />
            )
          }
        />
        <Route
          path="/"
          element={user ? <Chat user={user} /> : <Navigate to="/login" />}
        />
        <Route
          path="/admin"
          element={
            !user ? (
              <Navigate to="/login" />
            ) : user.is_admin ? (
              <Admin user={user} />
            ) : (
              <Navigate to="/" />
            )
          }
        />
      </Routes>
    </div>
  );
}

function NavBar({ user, onLogout }) {
  const navigate = useNavigate();
  return (
    <header className="navbar">
      <div className="brand">🔒 Knowledge Base</div>
      <nav>
        <Link to="/">Chat</Link>
        {user.is_admin && <Link to="/admin">Admin</Link>}
      </nav>
      <div className="nav-user">
        <span className="muted">
          {user.email}
          {` · ${user.roles.length > 0 ? user.roles.join(", ") : "customer"}`}
          {user.is_admin && " · admin"}
        </span>
        <button
          className="btn-secondary"
          onClick={() => {
            clearToken();
            onLogout();
            navigate("/login");
          }}
        >
          Log out
        </button>
      </div>
    </header>
  );
}
