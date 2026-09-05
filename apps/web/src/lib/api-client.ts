/**
 * Typed Frontend API Client for RecoveryOS API.
 * Reads backend URL from NEXT_PUBLIC_API_BASE_URL.
 */

export interface HealthResponse {
  status: string;
  service: string;
}

export interface DependenciesStatus {
  postgres: "connected" | "disconnected" | string;
  redis: "connected" | "disconnected" | string;
}

export interface ReadinessResponse {
  status: "ready" | "not_ready" | string;
  service: string;
  dependencies: DependenciesStatus;
  errors: string[];
}

export interface SystemHealthState {
  isChecking: boolean;
  isHealthy: boolean;
  healthData: HealthResponse | null;
  readinessData: ReadinessResponse | null;
  errorMessage: string | null;
  lastChecked: Date | null;
  latencyMs: number | null;
}

export interface UserResponse {
  id: string;
  email: string | null;
  email_verified: boolean | null;
  created_at: string;
}

export interface MerchantSummaryResponse {
  id: string;
  name: string;
  slug: string;
  role: "OWNER" | "ADMIN" | "OPERATOR" | "ANALYST" | "AUDITOR";
  status: "ACTIVE" | "SUSPENDED" | "REVOKED";
}

export interface MerchantResponse {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface MemberResponse {
  id: string;
  user_id: string;
  role: "OWNER" | "ADMIN" | "OPERATOR" | "ANALYST" | "AUDITOR";
  status: "ACTIVE" | "SUSPENDED" | "REVOKED";
  created_at: string;
}

const DEFAULT_API_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "");
  }
  return DEFAULT_API_URL;
}

export async function fetchApiHealth(baseUrl: string = getApiBaseUrl()): Promise<HealthResponse> {
  const response = await fetch(`${baseUrl}/health`, {
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}`);
  }

  return response.json();
}

export async function fetchApiReadiness(baseUrl: string = getApiBaseUrl()): Promise<ReadinessResponse> {
  const response = await fetch(`${baseUrl}/ready`, {
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });

  const data = await response.json();

  if (!response.ok && response.status !== 503) {
    throw new Error(`Readiness check failed with HTTP ${response.status}`);
  }

  return data;
}

export async function checkFullSystemStatus(
  baseUrl: string = getApiBaseUrl()
): Promise<{ health: HealthResponse; readiness: ReadinessResponse; latencyMs: number }> {
  const startTime = Date.now();
  const [health, readiness] = await Promise.all([
    fetchApiHealth(baseUrl),
    fetchApiReadiness(baseUrl),
  ]);
  const latencyMs = Date.now() - startTime;

  return { health, readiness, latencyMs };
}

export async function fetchCurrentUser(
  token: string,
  baseUrl: string = getApiBaseUrl()
): Promise<UserResponse> {
  const response = await fetch(`${baseUrl}/api/v1/me`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Authentication error HTTP ${response.status}`);
  }

  return response.json();
}

export async function fetchUserMerchants(
  token: string,
  baseUrl: string = getApiBaseUrl()
): Promise<MerchantSummaryResponse[]> {
  const response = await fetch(`${baseUrl}/api/v1/me/merchants`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to fetch merchants HTTP ${response.status}`);
  }

  return response.json();
}

export async function createMerchant(
  token: string,
  data: { name: string; slug: string },
  baseUrl: string = getApiBaseUrl()
): Promise<MerchantResponse> {
  const response = await fetch(`${baseUrl}/api/v1/merchants`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to create merchant HTTP ${response.status}`);
  }

  return response.json();
}

export async function fetchMerchantMembers(
  token: string,
  merchantId: string,
  baseUrl: string = getApiBaseUrl()
): Promise<MemberResponse[]> {
  const response = await fetch(`${baseUrl}/api/v1/merchants/${merchantId}/members`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to fetch members HTTP ${response.status}`);
  }

  return response.json();
}
