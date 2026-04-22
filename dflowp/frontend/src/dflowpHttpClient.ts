import type { HttpError } from "@refinedev/core";
import axios from "axios";
import { getDflowpApiKeyFromCookie } from "./dflowpApiKeyCookie";

const dflowpHttpClient = axios.create();

dflowpHttpClient.interceptors.request.use((config) => {
  const key = getDflowpApiKeyFromCookie();
  if (key) {
    config.headers = config.headers ?? {};
    config.headers["X-API-Key"] = key;
  }
  return config;
});

dflowpHttpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const customError: HttpError = {
      ...error,
      message: error.response?.data?.message,
      statusCode: error.response?.status,
    };
    return Promise.reject(customError);
  },
);

export { dflowpHttpClient };
