/**
 * Error normalization (04 §10): every rejection leaving the API layer is an
 * `ApiError` carrying `code`, `message`, `status`, optional `details`, and
 * (on 429) `retryAfter`. Views never see a raw axios error.
 */
import type { AxiosResponseHeaders } from "axios";

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
  retryAfter?: number;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: unknown;
  /** Parsed from the `Retry-After` response header on 429 (RFC 6585). */
  readonly retryAfter?: number;

  constructor(body: ApiErrorBody, status: number) {
    super(body.message);
    this.name = "ApiError";
    this.code = body.code;
    this.status = status;
    this.details = body.details;
    this.retryAfter = body.retryAfter;
  }

  /**
   * Normalize any error shape into an ApiError. Known shapes:
   * - 04 §10 envelope: `{"error": {code, message, details?}}`
   * - non-envelope JSON (offline proxy HTML, plain DRF bodies, empty bodies)
   */
  static fromResponse(
    status: number,
    data: unknown,
    headers?: Partial<AxiosResponseHeaders>,
  ): ApiError {
    let code = "UNKNOWN_ERROR";
    let message = "Something went wrong. Please try again.";
    let details: unknown;

    if (
      data !== null &&
      typeof data === "object" &&
      "error" in data &&
      data.error !== null &&
      typeof data.error === "object"
    ) {
      const envelope = data.error as Record<string, unknown>;
      if (typeof envelope.code === "string") code = envelope.code;
      if (typeof envelope.message === "string") message = envelope.message;
      if (envelope.details !== undefined) details = envelope.details;
      if (typeof envelope.retry_after_seconds === "number") {
        return new ApiError(
          { code, message, details, retryAfter: envelope.retry_after_seconds },
          status,
        );
      }
    } else if (typeof data === "string" && data.trim() !== "") {
      // HTML error pages (a 502 from a proxy, for example) — keep the status,
      // replace the body with something views can render.
      message = `Unexpected server response (HTTP ${status}).`;
    }

    let retryAfter: number | undefined;
    const rawRetryAfter = headers?.get?.("retry-after");
    const retryAfterText =
      rawRetryAfter === undefined || rawRetryAfter === null
        ? undefined
        : String(rawRetryAfter);
    if (status === 429 && retryAfterText !== undefined) {
      const parsed = Number.parseInt(retryAfterText, 10);
      if (!Number.isNaN(parsed)) {
        retryAfter = parsed;
      }
    }

    return new ApiError({ code, message, details, retryAfter }, status);
  }

  static network(message = "Network error. Check your connection and try again."): ApiError {
    return new ApiError({ code: "NETWORK_ERROR", message }, 0);
  }
}

/** Raised by the client when a session cannot be restored (terminal 401). */
export class SessionExpiredError extends ApiError {
  constructor() {
    super(
      {
        code: "SESSION_EXPIRED",
        message: "Your session has expired. Please sign in again.",
      },
      401,
    );
    this.name = "SessionExpiredError";
  }
}
