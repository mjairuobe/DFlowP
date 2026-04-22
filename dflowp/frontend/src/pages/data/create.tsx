import React, { useState } from "react";
import { useCreate, useNavigation, useNotification, useTranslate, type BaseRecord, type HttpError } from "@refinedev/core";
import { ListButton } from "@refinedev/mui";
import ArrowBack from "@mui/icons-material/ArrowBack";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { RefineListView } from "../../components";

const defaultPayload = `{
  "content": {},
  "type": "input"
}`;

export const DataCreate = () => {
  const t = useTranslate();
  const { show } = useNavigation();
  const { open: openNotification } = useNotification();
  const { mutate, mutation } = useCreate<
    BaseRecord,
    HttpError,
    Record<string, unknown>
  >({
    resource: "data",
    dataProviderName: "dflowp",
    successNotification: false,
    errorNotification: false,
  });
  const { isPending, error } = mutation;

  const [raw, setRaw] = useState(defaultPayload);
  const [parseError, setParseError] = useState<string | null>(null);

  const submit = () => {
    setParseError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : t("data.errors.jsonInvalid", "Ungültiges JSON."));
      return;
    }
    if (typeof parsed !== "object" || parsed === null) {
      setParseError(t("data.errors.bodyMustBeObject", "Der Body muss ein JSON-Objekt sein."));
      return;
    }
    const o = parsed as Record<string, unknown>;
    if (!("content" in o)) {
      setParseError(t("data.errors.contentRequired", "Feld \"content\" ist Pflicht (DataItemCreateRequest)."));
      return;
    }
    if (typeof o.content !== "object" || o.content === null) {
      setParseError(t("data.errors.contentMustBeObject", "\"content\" muss ein JSON-Objekt sein."));
      return;
    }

    mutate(
      { values: o },
      {
        onSuccess: (res) => {
          const newId =
            res.data && typeof res.data === "object" && "id" in res.data
              ? String((res.data as { id: string }).id)
              : undefined;
          openNotification?.({
            type: "success",
            message: t("data.create.saved", "Gespeichert."),
            description: newId
              ? t("data.create.openingDetail", { id: newId, defaultValue: "Objekt \"{{id}}\"" })
              : undefined,
          });
          if (newId) {
            show("data", newId);
          }
        },
      },
    );
  };

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
        title={t("data.titles.create", "Datenobjekt anlegen")}
        headerButtonProps={{}}
      >
        {parseError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setParseError(null)}>
            {parseError}
          </Alert>
        )}
        {error?.message && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error.message}
          </Alert>
        )}
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t(
            "data.create.hint",
            "Erwartet wird ein JSON-Objekt mit mindestens \"content\"; optional \"id\" und \"type\" (Standard \"input\").",
          )}
        </Typography>
        <TextField
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          fullWidth
          multiline
          minRows={22}
          spellCheck={false}
          inputProps={{ sx: { fontFamily: "ui-monospace, monospace" } }}
        />
        <Box sx={{ mt: 2 }}>
          <Button variant="contained" onClick={submit} disabled={isPending} size="large">
            {t("data.actions.create", "Anlegen")}
          </Button>
        </Box>
      </RefineListView>
    </>
  );
};
