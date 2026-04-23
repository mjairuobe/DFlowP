import React, { useMemo } from "react";
import { useShow, useTranslate, type BaseRecord, type HttpError } from "@refinedev/core";
import { ListButton } from "@refinedev/mui";
import { useParams } from "react-router";
import ArrowBack from "@mui/icons-material/ArrowBack";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Typography from "@mui/material/Typography";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { RefineListView } from "../../components";

export const DataShow = () => {
  const t = useTranslate();
  const { id: routeId } = useParams<{ id: string }>();
  const { query, result: doc } = useShow<BaseRecord, HttpError>({
    errorNotification: false,
  });

  const { isError, isPending, isFetching, error, refetch } = query;

  const jsonText = useMemo(() => {
    if (!doc) return "";
    try {
      return JSON.stringify(doc, null, 2);
    } catch {
      return String(doc);
    }
  }, [doc]);

  if (isPending && !doc) {
    return (
      <Box display="flex" justifyContent="center" py={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (isError && (error as HttpError)?.message) {
    return (
      <RefineListView
        title={
          <Typography variant="h5">
            {t("data.titles.show", "Datenobjekt")} {routeId ? `(${routeId})` : ""}
          </Typography>
        }
      >
        <Alert
          severity="error"
          onClose={() => {
            void refetch();
          }}
        >
          {(error as HttpError).message}
        </Alert>
        <ListButton
          resource="data"
          variant="outlined"
          sx={{ mt: 2, borderColor: "GrayText", color: "GrayText" }}
          startIcon={<ArrowBack />}
        />
      </RefineListView>
    );
  }

  return (
    <>
      <ListButton
        resource="data"
        variant="outlined"
        sx={{
          borderColor: "GrayText",
          color: "GrayText",
          backgroundColor: "transparent",
        }}
        startIcon={<ArrowBack />}
      />
      <Divider sx={{ my: 3 }} />
      <RefineListView
        title={
          <Typography variant="h5">
            {t("data.titles.show", "Datenobjekt")} {doc && "id" in doc ? ` — ${String(doc.id)}` : ""}
          </Typography>
        }
        headerButtonProps={{}}
      >
        {isFetching && (
          <Box display="flex" alignItems="center" gap={1} mb={2}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">
              {t("data.hints.refreshing", "Aktualisiere …")}
            </Typography>
          </Box>
        )}
        <Box
          sx={{
            maxHeight: "70vh",
            overflow: "auto",
            borderRadius: 1,
            border: 1,
            borderColor: "divider",
            "& pre": { margin: 0, borderRadius: 1 },
          }}
        >
          <SyntaxHighlighter
            language="json"
            style={vscDarkPlus}
            showLineNumbers
            wrapLongLines
            customStyle={{ margin: 0, borderRadius: 4 }}
          >
            {jsonText}
          </SyntaxHighlighter>
        </Box>
      </RefineListView>
    </>
  );
};
