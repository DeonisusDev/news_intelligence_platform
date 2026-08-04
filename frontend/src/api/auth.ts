const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface CurrentUser {
  id: number;
  email: string;
}

export class AuthError extends Error {}

// `credentials: "include"` on every call - the session lives in an httpOnly cookie the browser
// manages, never a token this code touches directly.

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, { credentials: "include" });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(`Failed to load session (${response.status})`);
  return response.json();
}

export async function register(email: string, password: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new AuthError(
      response.status === 409 ? "That email is already registered." : "Registration failed."
    );
  }
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new AuthError(
      response.status === 401 ? "Incorrect email or password." : "Login failed."
    );
  }
  return response.json();
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", credentials: "include" });
}
