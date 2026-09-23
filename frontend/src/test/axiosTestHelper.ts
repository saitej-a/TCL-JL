/**
 * Test helper (D8: no mocking dependency — the axios instance's adapter is
 * swapped for a scripted fake). Shared by the client and context suites.
 */
import type { AxiosAdapter, AxiosRequestConfig } from "axios";

import { apiClient } from "@/api/client";

export interface ScriptedCall {
  /** Match the URL suffix (after the baseURL), e.g. "/auth/token/refresh/". */
  url: string;
  method?: string;
  respond: (config: AxiosRequestConfig) => {
    status: number;
    data?: unknown;
    headers?: Record<string, string>;
  };
}

export function scriptAdapter(script: ScriptedCall[]): { calls: AxiosRequestConfig[] } {
  const calls: AxiosRequestConfig[] = [];
  let cursor = 0;
  const adapter: AxiosAdapter = (config) => {
    calls.push(config);
    const step = script[cursor];
    cursor += 1;
    if (step === undefined) {
      return Promise.reject(new Error(`unexpected request #${cursor}: ${String(config.url)}`));
    }
    if (
      step.method !== undefined &&
      config.method?.toLowerCase() !== step.method.toLowerCase()
    ) {
      return Promise.reject(
        new Error(`expected ${step.method}, got ${String(config.method)} for ${String(config.url)}`),
      );
    }
    if (!String(config.url).endsWith(step.url)) {
      return Promise.reject(
        new Error(`expected url to end with ${step.url}, got ${String(config.url)}`),
      );
    }
    const answer = step.respond(config);
    const response = {
      data: answer.data,
      status: answer.status,
      statusText: "",
      headers: answer.headers ?? {},
      config,
      request: {},
    };
    if (answer.status >= 200 && answer.status < 300) {
      return Promise.resolve(response);
    }
    // Axios rejects non-2xx with an AxiosError-shaped object.
    const error = new Error(`Request failed with status code ${answer.status}`) as Error & {
      config: unknown;
      response: unknown;
      isAxiosError: boolean;
    };
    error.config = config;
    error.response = response;
    error.isAxiosError = true;
    return Promise.reject(error);
  };
  apiClient.defaults.adapter = adapter;
  return { calls };
}
