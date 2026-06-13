/**
 * Base URL for the invoce backend API.
 *
 * Read from the public env var NEXT_PUBLIC_API_BASE_URL so it can be
 * configured per environment (see .env.local.example). Falls back to the
 * local backend default when unset.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
