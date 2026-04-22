/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_MAP_ID: string;
  /** Optional: Base URL für Refine dataProvider; Standard bleibt die Finefoods-Demo-API. */
  readonly VITE_DFLOWP_API_BASE_URL?: string;
}
