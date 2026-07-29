import axios from "axios";

const TOKEN_KEY = "kb_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// Axios instance that automatically attaches the JWT to every request.
export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function devLogin({ email, name, roles, is_admin }) {
  const { data } = await api.post("/auth/dev-login", {
    email,
    name,
    roles,
    is_admin,
  });
  setToken(data.access_token);
  return data;
}

export async function fetchAuthConfig() {
  const { data } = await api.get("/auth/config");
  return data;
}

// Full-page redirect into the Google OAuth flow (not an axios/XHR call).
export function googleLoginUrl() {
  return "/api/auth/google/login";
}

// After the OAuth redirect, the backend returns the JWT in the URL fragment
// (#token=...). Capture it, store it, and clean the URL. Returns an error code
// if the flow failed, or null.
export function consumeAuthHash() {
  const hash = window.location.hash.replace(/^#/, "");
  if (!hash) return null;
  const params = new URLSearchParams(hash);
  const token = params.get("token");
  const error = params.get("error");
  if (token || error) {
    // Strip the fragment so the token isn't left sitting in the address bar.
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  if (token) setToken(token);
  return error;
}

export async function fetchMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

// ---- User management (admin) ----
export async function listUsers() {
  const { data } = await api.get("/users");
  return data;
}

export async function updateUser(id, { roles, is_admin }) {
  const { data } = await api.patch(`/users/${id}`, { roles, is_admin });
  return data;
}

// ---- Audit log (admin) ----
export async function listAuditLogs({ action, actorEmail, limit } = {}) {
  const params = {};
  if (action) params.action = action;
  if (actorEmail) params.actor_email = actorEmail;
  if (limit) params.limit = limit;
  const { data } = await api.get("/audit", { params });
  return data;
}

export async function listDocuments() {
  const { data } = await api.get("/documents");
  return data;
}

export async function uploadDocument(file, allowedRoles) {
  const form = new FormData();
  form.append("file", file);
  form.append("allowed_roles", allowedRoles);
  const { data } = await api.post("/documents/ingest", form);
  return data;
}

// Re-tag a document's allowed roles after upload. `roles` is an array of strings
// (empty = visible to everyone).
export async function updateDocument(id, roles) {
  const { data } = await api.patch(`/documents/${id}`, { allowed_roles: roles });
  return data;
}

export async function deleteDocument(id) {
  await api.delete(`/documents/${id}`);
}

// Stream an answer. Calls onCitations(list) once, then onToken(text) per token.
export async function askStream(query, { onCitations, onToken }) {
  const res = await fetch("/api/chat/ask/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newlineIndex;
    while ((newlineIndex = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (!line) continue;
      const event = JSON.parse(line);
      if (event.type === "citations") onCitations?.(event.data);
      else if (event.type === "token") onToken?.(event.data);
    }
  }
}
