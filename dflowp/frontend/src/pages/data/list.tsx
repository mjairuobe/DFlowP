import React, { useMemo } from "react";
import { type HttpError, useNavigation, useTranslate } from "@refinedev/core";
import { CreateButton, useDataGrid } from "@refinedev/mui";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import Typography from "@mui/material/Typography";
import type { IDataListItem } from "../../interfaces";
import { RefineListView } from "../../components";

const dateTimeFormatDe = new Intl.DateTimeFormat("de-DE", {
  dateStyle: "medium",
  timeStyle: "medium",
});

export const DataList = () => {
  const t = useTranslate();
  const { show } = useNavigation();

  const { dataGridProps } = useDataGrid<IDataListItem, HttpError>({
    resource: "data",
    pagination: {
      pageSize: 20,
    },
  });

  const columns = useMemo<GridColDef<IDataListItem>[]>(
    () => [
      {
        field: "timestamp_ms",
        width: 144,
        headerName: t("data.fields.timestamp", "Zeitstempel"),
        display: "flex",
        sortable: false,
        valueGetter: (_, row) => row.timestamp_ms,
        renderCell: ({ row }) => (
          <Typography variant="body2">
            {typeof row.timestamp_ms === "number"
              ? dateTimeFormatDe.format(new Date(row.timestamp_ms))
              : "—"}
          </Typography>
        ),
      },
      {
        field: "id",
        width: 225,
        headerName: t("data.fields.objectId", "Datenobjekt-ID"),
        display: "flex",
        sortable: false,
      },
      {
        field: "doc_type",
        width: 140,
        headerName: t("data.fields.docType", "Dokumententyp"),
        display: "flex",
        sortable: false,
      },
    ],
    [t],
  );

  return (
    <RefineListView
      headerButtons={
        <CreateButton
          resource="data"
          size="medium"
          sx={{ height: "40px" }}
          variant="outlined"
        >
          {t("data.actions.create", "Anlegen")}
        </CreateButton>
      }
    >
      <DataGrid
        {...dataGridProps}
        columns={columns}
        getRowId={(row) => row.id}
        onRowClick={({ id }) => {
          show("data", String(id));
        }}
        pageSizeOptions={[10, 20, 50, 100]}
        sx={{
          "& .MuiDataGrid-row": {
            cursor: "pointer",
          },
        }}
      />
    </RefineListView>
  );
};
