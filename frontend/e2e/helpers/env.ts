/** Shared environment configuration for the Playwright E2E suite. */

export const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:5173";
export const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";
