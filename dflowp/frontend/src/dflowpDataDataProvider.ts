import type { BaseRecord, DataProvider, GetListParams, GetListResponse, HttpError } from "@refinedev/core";
import type { AxiosInstance } from "axios";
import { dflowpHttpClient } from "./dflowpHttpClient";

const DFLOWP_DATA_PATH = "/api/v1/data";

const unsupported: HttpError = {
  message: "Für Data-Objekte sind weder Update noch Löschen vorgesehen.",
  statusCode: 405,
};

/**
 * Data-Provider ausschließlich für die Ressource `data` → DFlowP `GET/POST /api/v1/data`.
 * Als einziger `dataProvider` in `<Refine>` für die Ressource `data` nutzen.
 */
export const createDflowpDataDataProvider = (
  apiBase: string,
  httpClient: AxiosInstance = dflowpHttpClient,
): DataProvider => ({
  getApiUrl: () => apiBase.replace(/\/$/, ""),

  getList: async <TData extends BaseRecord = BaseRecord>({
    resource,
    pagination,
    meta,
  }: GetListParams): Promise<GetListResponse<TData>> => {
    if (resource !== "data") {
      const err: HttpError = { message: `Ressource "${resource}" unbekannt.`, statusCode: 400 };
      throw err;
    }
    const { currentPage = 1, pageSize = 20, mode = "server" } = pagination ?? {};
    const params = new URLSearchParams();
    if (mode === "server") {
      params.set("page", String(currentPage));
      params.set("page_size", String(pageSize));
    }
    const extra = (meta?.query as Record<string, string | string[] | number | boolean | undefined>) || {};
    for (const [k, v] of Object.entries(extra)) {
      if (v === undefined) continue;
      if (Array.isArray(v)) {
        for (const item of v) {
          params.append(k, String(item));
        }
      } else {
        params.set(k, String(v));
      }
    }
    const base = apiBase.replace(/\/$/, "");
    const qs = params.toString();
    const url = `${base}${DFLOWP_DATA_PATH}${qs ? `?${qs}` : ""}`;
    const { data: raw } = await httpClient.get<{
      items: TData[];
      total_items: number;
    }>(url);
    return {
      data: raw.items,
      total: raw.total_items,
    };
  },

  getOne: async ({ resource, id, meta }) => {
    if (resource !== "data") {
      const err: HttpError = { message: `Ressource "${resource}" unbekannt.`, statusCode: 400 };
      throw err;
    }
    const base = apiBase.replace(/\/$/, "");
    const { data } = await httpClient.get(
      `${base}${DFLOWP_DATA_PATH}/${encodeURIComponent(String(id))}`,
      { headers: (meta as { headers?: Record<string, string> })?.headers },
    );
    return { data };
  },

  create: async ({ resource, variables, meta }) => {
    if (resource !== "data") {
      const err: HttpError = { message: `Ressource "${resource}" unbekannt.`, statusCode: 400 };
      throw err;
    }
    const base = apiBase.replace(/\/$/, "");
    const { data } = await httpClient.post(
      `${base}${DFLOWP_DATA_PATH}`,
      variables,
      { headers: (meta as { headers?: Record<string, string> })?.headers },
    );
    return { data };
  },

  update: async () => {
    throw unsupported;
  },

  deleteOne: async () => {
    throw unsupported;
  },
});
