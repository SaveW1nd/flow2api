import { API_V1 } from "./config";

const ACCESS_KEY = "f2a_access";
const REFRESH_KEY = "f2a_refresh";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function refreshToken(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return false;
  const res = await fetch(`${API_V1}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return true;
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_V1}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    const ok = await refreshToken();
    if (ok) return api<T>(path, options, false);
    clearTokens();
    if (typeof window !== "undefined") window.location.href = "/";
    throw new ApiError("登录已失效", 401);
  }

  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---------- Auth ----------
export async function login(email: string, password: string) {
  const data = await api<{ access_token: string; refresh_token: string }>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) }
  );
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function register(email: string, password: string, full_name?: string) {
  return api("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name }),
  });
}

export interface Me {
  id: number;
  email: string;
  full_name: string | null;
  role: "user" | "admin";
  daily_image_quota: number;
  daily_video_quota: number;
}

export const getMe = () => api<Me>("/auth/me");
