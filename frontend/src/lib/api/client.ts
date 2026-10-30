const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback: (token: string) => void) {
  refreshSubscribers.push(callback);
}

export async function ensureAuthToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const existingToken = localStorage.getItem("token");
  if (existingToken) return existingToken;

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "admin@marketing-os.local",
        password: "admin123",
      }),
    });
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem("token", data.access_token);
      if (data.refresh_token) {
        localStorage.setItem("refreshToken", data.refresh_token);
      }
      localStorage.setItem(
        "user",
        JSON.stringify({
          id: "00000000-0000-0000-0000-000000000001",
          email: "admin@marketing-os.local",
          role: data.role || "admin",
          full_name: "Admin User",
          accessToken: data.access_token,
        })
      );
      return data.access_token;
    }
  } catch {}
  return null;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  let token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (!token && !endpoint.includes("/auth/")) {
    token = await ensureAuthToken();
  }

  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
  let response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401 && typeof window !== "undefined" && !endpoint.includes("/auth/")) {
    const refreshToken = localStorage.getItem("refreshToken");
    if (refreshToken) {
      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (refreshRes.ok) {
            const data = await refreshRes.json();
            token = data.access_token;
            localStorage.setItem("token", data.access_token);
            if (data.refresh_token) {
              localStorage.setItem("refreshToken", data.refresh_token);
            }
            onRefreshed(data.access_token);
          } else {
            localStorage.removeItem("token");
            localStorage.removeItem("refreshToken");
            localStorage.removeItem("user");
            token = await ensureAuthToken();
          }
        } finally {
          isRefreshing = false;
        }
      } else {
        token = await new Promise<string>((resolve) => {
          addRefreshSubscriber(resolve);
        });
      }
    } else {
      token = await ensureAuthToken();
    }

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
      response = await fetch(url, {
        ...options,
        headers,
      });
    }
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error [${response.status}]: ${errorText}`);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json();
}
