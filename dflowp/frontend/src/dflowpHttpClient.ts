import type { HttpError } from "@refinedev/core";
import axios from "axios";
import { getDflowpApiKeyForHeader } from "./dflowpApiKeyCookie";

const dflowpHttpClient = axios.create();

dflowpHttpClient.interceptors.request.use((config) => {
  const key = getDflowpApiKeyForHeader();
  if (key) {
    config.headers = config.headers ?? {};
    config.headers["X-API-Key"] = key;
  }
  return config;
});

function messageFromResponseData(data: unknown): string | undefined {
  if (data == null || typeof data !== "object") return undefined;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  if (Array.isArray(d.detail)) {
    return d.detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: string }).msg);
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (typeof d.message === "string") return d.message;
  return undefined;
}

dflowpHttpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const fromBody = error.response?.data
      ? messageFromResponseData(error.response.data)
      : undefined;
    const customError: HttpError = {
      ...error,
      message: fromBody || error.message,
      statusCode: error.response?.status,
    };
    return Promise.reject(customError);
  },
);

export { dflowpHttpClient };
