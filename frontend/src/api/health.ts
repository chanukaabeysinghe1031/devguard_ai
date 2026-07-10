export type BackendHealth = {
  status: string;
  service: string;
  version: string;
};

export type BackendStatus = "loading" | "online" | "offline";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!apiBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not defined");
}

export async function fetchBackendHealth(): Promise<BackendHealth> {
  const response = await fetch(`${apiBaseUrl}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json() as Promise<BackendHealth>;
}
