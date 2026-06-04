import type { TokenResponse } from "@/types";

const ACCESS_TOKEN_KEY = "penkeep_access_token";
const REFRESH_TOKEN_KEY = "penkeep_refresh_token";

function canUseStorage() {
  return typeof window !== "undefined";
}

export function getStoredAccessToken() {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken() {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens(tokens: Pick<TokenResponse, "access_token" | "refresh_token">) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearStoredTokens() {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}
