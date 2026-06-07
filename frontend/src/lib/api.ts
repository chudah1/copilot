import { getApiBaseUrl } from "./api-base";
import { getStoredAccessToken, getStoredRefreshToken, storeTokens, clearStoredTokens } from "./auth-tokens";

class ApiClient {
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const apiUrl = getApiBaseUrl();
    const accessToken = getStoredAccessToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(options.headers as Record<string, string>),
    };

    const response = await fetch(`${apiUrl}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });

    if (response.status === 401) {
      // Auth endpoints never need a refresh — surface the real error directly.
      const isAuthEndpoint = path.startsWith("/api/auth/login") || path.startsWith("/api/auth/register");
      if (isAuthEndpoint || !accessToken) {
        const body = await response.json().catch(() => ({}));
        const detail = body.detail;
        const message = typeof detail === "string" && detail !== "Invalid credentials"
          ? detail
          : "Incorrect email or password";
        throw new Error(message);
      }
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        const retryAccessToken = getStoredAccessToken();
        const retry = await fetch(`${apiUrl}${path}`, {
          ...options,
          headers: {
            ...headers,
            ...(retryAccessToken ? { Authorization: `Bearer ${retryAccessToken}` } : {}),
          },
          credentials: "include",
        });
        if (!retry.ok) throw new Error("Something went wrong. Please try again.");
        return retry.json();
      }
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Session expired");
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = body.detail;
      const message = Array.isArray(detail)
        ? detail.map((e: { msg?: string }) => e.msg ?? String(e)).join("; ")
        : typeof detail === "string"
        ? detail
        : "Something went wrong. Please try again.";
      throw new Error(message);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  private async tryRefresh(): Promise<boolean> {
    const apiUrl = getApiBaseUrl();
    try {
      const response = await fetch(`${apiUrl}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: getStoredRefreshToken() }),
        credentials: "include",
      });
      if (response.ok) {
        const tokens = await response.json();
        storeTokens(tokens);
        return true;
      }
      clearStoredTokens();
      return response.ok;
    } catch {
      return false;
    }
  }

  get<T>(path: string) {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown, init?: { signal?: AbortSignal }) {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      ...(init?.signal ? { signal: init.signal } : {}),
    });
  }

  put<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: "PUT", body: JSON.stringify(body) });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: "DELETE" });
  }
}

export const api = new ApiClient();
export const fetcher = <T>(path: string): Promise<T> => api.get<T>(path);
