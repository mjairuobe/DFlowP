import React, { type CSSProperties } from "react";
import {
  useIsExistAuthentication,
  useLogout,
  useTranslate,
  useLink,
  useWarnAboutChange,
} from "@refinedev/core";
import {
  type RefineThemedLayoutSiderProps,
  ThemedTitle as DefaultTitle,
  useThemedLayoutContext,
} from "@refinedev/mui";
import { useLocation } from "react-router";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Tooltip from "@mui/material/Tooltip";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import ShoppingBagOutlinedIcon from "@mui/icons-material/ShoppingBagOutlined";
import Logout from "@mui/icons-material/Logout";
import ChevronLeft from "@mui/icons-material/ChevronLeft";

const ordersPath = "/orders";

/**
 * Sidenav with only “Bestellungen” and “Abmelden” (no resource-driven menu list).
 */
export const MinimalSider: React.FC<RefineThemedLayoutSiderProps> = ({
  Title: TitleFromProps,
}) => {
  const {
    siderCollapsed,
    setSiderCollapsed,
    mobileSiderOpen,
    setMobileSiderOpen,
  } = useThemedLayoutContext();

  const { pathname } = useLocation();

  const drawerWidth = () => {
    if (siderCollapsed) return 56;
    return 240;
  };

  const t = useTranslate();
  const Link = useLink();
  const isExistAuthentication = useIsExistAuthentication();
  const { warnWhen, setWarnWhen } = useWarnAboutChange();
  const { mutate: mutateLogout } = useLogout();

  const RenderToTitle = TitleFromProps ?? DefaultTitle;

  const ordersSelected =
    pathname === ordersPath || pathname.startsWith(`${ordersPath}/`);

  const linkStyle: CSSProperties = {};
  const handleLogout = () => {
    if (warnWhen) {
      const confirm = window.confirm(
        t(
          "warnWhenUnsavedChanges",
          "Are you sure you want to leave? You have unsaved changes.",
        ),
      );
      if (confirm) {
        setWarnWhen(false);
        mutateLogout();
      }
    } else {
      mutateLogout();
    }
  };

  const ordersItem = (
    <Tooltip
      title={t("orders.orders", "Orders")}
      placement="right"
      disableHoverListener={!siderCollapsed}
      arrow
    >
      <ListItemButton
        component={Link as React.ElementType}
        to={ordersPath}
        selected={ordersSelected}
        style={linkStyle}
        onClick={() => {
          setMobileSiderOpen(false);
        }}
        sx={{
          pl: 2,
          py: 1,
          justifyContent: "center",
          color: ordersSelected ? "primary.main" : "text.primary",
        }}
      >
        <ListItemIcon
          sx={{
            justifyContent: "center",
            transition: "margin-right 0.3s",
            marginRight: siderCollapsed ? "0px" : "12px",
            minWidth: "24px",
            color: "currentColor",
          }}
        >
          <ShoppingBagOutlinedIcon />
        </ListItemIcon>
        <ListItemText
          primary={t("orders.orders", "Orders")}
          primaryTypographyProps={{
            noWrap: true,
            fontSize: "14px",
          }}
        />
      </ListItemButton>
    </Tooltip>
  );

  const logout = isExistAuthentication && (
    <Tooltip
      title={t("buttons.logout", "Logout")}
      placement="right"
      disableHoverListener={!siderCollapsed}
      arrow
    >
      <ListItemButton
        key="logout"
        onClick={() => handleLogout()}
        sx={{
          justifyContent: "center",
        }}
      >
        <ListItemIcon
          sx={{
            justifyContent: "center",
            minWidth: "24px",
            transition: "margin-right 0.3s",
            marginRight: siderCollapsed ? "0px" : "12px",
            color: "currentColor",
          }}
        >
          <Logout />
        </ListItemIcon>
        <ListItemText
          primary={t("buttons.logout", "Logout")}
          primaryTypographyProps={{
            noWrap: true,
            fontSize: "14px",
          }}
        />
      </ListItemButton>
    </Tooltip>
  );

  const drawer = (
    <List
      disablePadding
      sx={{
        flexGrow: 1,
        paddingTop: "16px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {ordersItem}
      {logout}
    </List>
  );

  return (
    <>
      <Box
        sx={{
          width: { xs: drawerWidth() },
          display: {
            xs: "none",
            md: "block",
          },
          transition: "width 0.3s ease",
        }}
      />
      <Box
        component="nav"
        sx={{
          position: "fixed",
          zIndex: 1101,
          width: { sm: drawerWidth() },
          display: "flex",
        }}
      >
        <Drawer
          variant="temporary"
          elevation={2}
          open={mobileSiderOpen}
          onClose={() => setMobileSiderOpen(false)}
          ModalProps={{
            keepMounted: true,
          }}
          sx={{
            display: {
              sm: "block",
              md: "none",
            },
          }}
        >
          <Box
            sx={{
              width: drawerWidth(),
            }}
          >
            <Box
              sx={{
                height: 64,
                display: "flex",
                alignItems: "center",
                paddingLeft: "16px",
                fontSize: "14px",
              }}
            >
              <RenderToTitle collapsed={false} />
            </Box>
            {drawer}
          </Box>
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: "none", md: "block" },
            "& .MuiDrawer-paper": {
              width: drawerWidth(),
              overflow: "hidden",
              transition: "width 200ms cubic-bezier(0.4, 0, 0.6, 1) 0ms",
            },
          }}
          open
        >
          <Paper
            elevation={0}
            sx={{
              fontSize: "14px",
              width: "100%",
              height: 64,
              display: "flex",
              flexShrink: 0,
              alignItems: "center",
              justifyContent: siderCollapsed ? "center" : "space-between",
              paddingLeft: siderCollapsed ? 0 : "16px",
              paddingRight: siderCollapsed ? 0 : "8px",
              variant: "outlined",
              borderRadius: 0,
              borderBottom: (theme) =>
                `1px solid ${theme.palette.action.focus}`,
            }}
          >
            <RenderToTitle collapsed={siderCollapsed} />
            {!siderCollapsed && (
              <IconButton size="small" onClick={() => setSiderCollapsed(true)}>
                <ChevronLeft />
              </IconButton>
            )}
          </Paper>
          <Box
            sx={{
              flexGrow: 1,
              overflowX: "hidden",
              overflowY: "auto",
            }}
          >
            {drawer}
          </Box>
        </Drawer>
      </Box>
    </>
  );
};
