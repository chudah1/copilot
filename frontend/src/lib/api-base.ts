const DEFAULT_API_PORT = "8000";
const PRODUCTION_API_URL = "https://api.penkeep.io";

export function getApiBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) {
    const withProtocol = configured.startsWith("http://") || configured.startsWith("https://")
      ? configured
      : `https://${configured}`;
    return withProtocol.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return `${protocol}//${hostname}:${DEFAULT_API_PORT}`;
    }
  }

  return process.env.NODE_ENV === "production"
    ? PRODUCTION_API_URL
    : `http://localhost:${DEFAULT_API_PORT}`;
}
