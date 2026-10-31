// Admin actions spend LLM credit, so the API wants a shared token (X-Admin-Token). It's kept in
// this browser only, entered once by whoever runs the dashboard.
const TOKEN_KEY = "race-watcher.admin-token";

export function readToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveToken(token: string) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Private mode etc.: the token just won't be remembered.
  }
}
