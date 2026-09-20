export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public hint?: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    let body: unknown = {};
    try {
      body = await response.json();
    } catch {}
    const parsed = body as { detail?: { code?: string; message?: string; hint?: string } };
    const detail = parsed.detail || {};
    throw new ApiError(
      response.status,
      detail.code || "request_failed",
      detail.message || response.statusText,
      detail.hint,
    );
  }
  return response.json() as Promise<T>;
}
