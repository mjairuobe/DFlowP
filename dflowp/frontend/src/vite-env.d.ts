/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_MAP_ID: string;
  /** Testkonfiguration: Wert landet im Cookie + X-API-Key (siehe dflowpApiKeyCookie / authProvider). */
  readonly VITE_DFLOWP_API_KEY?: string;
  /** Optional: Base URL für Refine dataProvider; Standard bleibt die Finefoods-Demo-API. */
  readonly VITE_DFLOWP_API_BASE_URL?: string;
}
