type BackendUrlOptions = {
  backendUrl?: string;
  publicApiUrl?: string;
  nodeEnv?: string;
};

const LOCAL_BACKEND_URL = "http://localhost:8000";
const PRODUCTION_BACKEND_URL = "https://api.penkeep.io";

function normaliseConfiguredUrl(value: string | undefined) {
  const trimmed = value?.trim();
  if (!trimmed) return null;
  const withProtocol = trimmed.startsWith("http://") || trimmed.startsWith("https://")
    ? trimmed
    : `https://${trimmed}`;
  return withProtocol.replace(/\/+$/, "");
}

export function resolveBackendApiUrl({
  backendUrl = process.env.BACKEND_API_URL,
  publicApiUrl = process.env.NEXT_PUBLIC_API_URL,
  nodeEnv = process.env.NODE_ENV,
}: BackendUrlOptions = {}) {
  return (
    normaliseConfiguredUrl(backendUrl) ??
    normaliseConfiguredUrl(publicApiUrl) ??
    (nodeEnv === "production" ? PRODUCTION_BACKEND_URL : LOCAL_BACKEND_URL)
  );
}
