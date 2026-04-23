export interface IIdentity {
  id: number;
  name: string;
  avatar: string;
}

/** Eintrag aus GET /api/v1/data (ohne top-level `content`). */
export interface IDataListItem {
  id: string;
  doc_type: "data" | "dataset";
  timestamp_ms?: number;
  _id?: string;
}
