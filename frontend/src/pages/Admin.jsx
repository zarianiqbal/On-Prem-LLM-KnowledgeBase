import { useEffect, useState } from "react";
import {
  deleteDocument,
  listDocuments,
  listUsers,
  updateUser,
  uploadDocument,
} from "../api";

export default function Admin({ user }) {
  const [docs, setDocs] = useState([]);
  const [file, setFile] = useState(null);
  const [roles, setRoles] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setDocs(await listDocuments());
  }

  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setStatus("");
    try {
      const res = await uploadDocument(file, roles);
      setStatus(
        `✅ Ingested "${res.document.filename}" — ${res.chunks_created} chunks.`
      );
      setFile(null);
      setRoles("");
      e.target.reset();
      await refresh();
    } catch (err) {
      setStatus(`⚠️ ${err?.response?.data?.detail || err.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id) {
    await deleteDocument(id);
    await refresh();
  }

  return (
    <div className="admin">
      <div className="card">
        <h2>Upload a document</h2>
        <p className="muted">
          Choose which roles may access it. Leave blank to make it visible to all
          authenticated users. Chunks are tagged with these roles and filtered on
          every query — the LLM never sees documents outside a user's access.
        </p>
        <form onSubmit={handleUpload}>
          <label>File (.pdf, .docx, .txt, .md)</label>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => setFile(e.target.files[0])}
            required
          />

          <label>Allowed roles (comma-separated)</label>
          <input
            value={roles}
            onChange={(e) => setRoles(e.target.value)}
            placeholder="hr, finance   (blank = everyone)"
          />

          <button className="btn-primary" disabled={busy || !file}>
            {busy ? "Ingesting…" : "Upload & ingest"}
          </button>
        </form>
        {status && <div className="status">{status}</div>}
      </div>

      <div className="card">
        <h2>Documents ({docs.length})</h2>
        {docs.length === 0 && <p className="muted">No documents yet.</p>}
        <table className="doc-table">
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>
                  <strong>{d.filename}</strong>
                  <div className="muted small">
                    {d.num_chunks} chunks ·{" "}
                    {d.allowed_roles.length
                      ? d.allowed_roles.join(", ")
                      : "everyone"}
                  </div>
                </td>
                <td className="right">
                  <button
                    className="btn-danger"
                    onClick={() => handleDelete(d.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <UsersPanel currentEmail={user?.email} />
    </div>
  );
}

// Assign roles / admin to users. New Google users arrive with no roles (treated
// as "customer" — least privilege) until an admin assigns them here.
function UsersPanel({ currentEmail }) {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      setUsers(await listUsers());
    } catch (err) {
      setError(err?.response?.data?.detail || err.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function save(u, roles, isAdmin) {
    setError("");
    try {
      const updated = await updateUser(u.id, {
        roles: roles
          .split(",")
          .map((r) => r.trim())
          .filter(Boolean),
        is_admin: isAdmin,
      });
      setUsers((list) => list.map((x) => (x.id === updated.id ? updated : x)));
    } catch (err) {
      setError(err?.response?.data?.detail || err.message);
      refresh();
    }
  }

  return (
    <div className="card">
      <h2>Users ({users.length})</h2>
      <p className="muted">
        Assign roles (comma-separated) to control what each person can see. A user
        with no roles is a <strong>customer</strong> — the least-privileged tier,
        who sees only public documents and anything tagged <code>customer</code>.
      </p>
      {error && <div className="error">{error}</div>}
      <table className="doc-table">
        <tbody>
          {users.map((u) => (
            <UserRow
              key={u.id}
              user={u}
              isSelf={u.email === currentEmail}
              onSave={save}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UserRow({ user, isSelf, onSave }) {
  const [roles, setRoles] = useState(user.roles.join(", "));
  const [isAdmin, setIsAdmin] = useState(user.is_admin);

  const dirty = roles !== user.roles.join(", ") || isAdmin !== user.is_admin;

  return (
    <tr>
      <td>
        <strong>{user.name || user.email}</strong>
        {isSelf && <span className="muted small"> (you)</span>}
        <div className="muted small">{user.email}</div>
      </td>
      <td>
        <input
          value={roles}
          onChange={(e) => setRoles(e.target.value)}
          placeholder="customer"
        />
      </td>
      <td>
        <label className="checkbox" style={{ margin: 0 }}>
          <input
            type="checkbox"
            checked={isAdmin}
            onChange={(e) => setIsAdmin(e.target.checked)}
          />
          admin
        </label>
      </td>
      <td className="right">
        <button
          className="btn-primary"
          disabled={!dirty}
          onClick={() => onSave(user, roles, isAdmin)}
        >
          Save
        </button>
      </td>
    </tr>
  );
}
