import { ApiError } from "@/lib/api";
export function ErrorState({ error }: { error: unknown }) {
  const apiError = error as ApiError;
  return (
    <div className="panel error">
      <strong>{apiError.code || "request_failed"}</strong>
      <div>{apiError.message}</div>
      {apiError.hint && <small>{apiError.hint}</small>}
    </div>
  );
}
