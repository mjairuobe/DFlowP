import { Authenticated, GitHubBanner, Refine } from "@refinedev/core";
import {
  ErrorComponent,
  useNotificationProvider,
  ThemedLayout,
  RefineSnackbarProvider,
} from "@refinedev/mui";
import GlobalStyles from "@mui/material/GlobalStyles";
import CssBaseline from "@mui/material/CssBaseline";
import simpleRest from "@refinedev/simple-rest";
import { dflowpHttpClient } from "./dflowpHttpClient";
import { createDflowpDataDataProvider } from "./dflowpDataDataProvider";
import routerProvider, {
  CatchAllNavigate,
  NavigateToResource,
  UnsavedChangesNotifier,
  DocumentTitleHandler,
} from "@refinedev/react-router";
import { BrowserRouter, Routes, Route, Outlet } from "react-router";
import { useTranslation } from "react-i18next";
import ShoppingBagOutlinedIcon from "@mui/icons-material/ShoppingBagOutlined";
import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";
import Box from "@mui/material/Box";
import { authProvider } from "./authProvider";
import { DashboardPage } from "./pages/dashboard";
import { OrderList, OrderShow } from "./pages/orders";
import { DataCreate, DataList, DataShow } from "./pages/data";
import { AuthPage } from "./pages/auth";
import { ColorModeContextProvider } from "./contexts";
import { Header, Title } from "./components";
import { MinimalSider } from "./components/sider";

const ORDERS_API_URL =
  import.meta.env.VITE_ORDERS_API_BASE_URL || "https://api.finefoods.refine.dev";
const DFLOWP_API_BASE_URL = import.meta.env.VITE_DFLOWP_API_BASE_URL || "";

const ordersDataProvider = simpleRest(ORDERS_API_URL, dflowpHttpClient);
const dflowpDataDataProvider = createDflowpDataDataProvider(DFLOWP_API_BASE_URL, dflowpHttpClient);

const App: React.FC = () => {
  const { t, i18n } = useTranslation();
  const i18nProvider = {
    translate: (key: string, params: object) => t(key, params),
    changeLocale: (lang: string) => i18n.changeLanguage(lang),
    getLocale: () => i18n.language,
  };

  return (
    <BrowserRouter>
      <GitHubBanner />
      <ColorModeContextProvider>
        <CssBaseline />
        <GlobalStyles styles={{ html: { WebkitFontSmoothing: "auto" } }} />
        <RefineSnackbarProvider>
          <Refine
            routerProvider={routerProvider}
            dataProvider={{
              default: ordersDataProvider,
              dflowp: dflowpDataDataProvider,
            }}
            authProvider={authProvider}
            i18nProvider={i18nProvider}
            options={{
              syncWithLocation: true,
              warnWhenUnsavedChanges: true,
              breadcrumb: false,
            }}
            notificationProvider={useNotificationProvider}
            resources={[
              {
                name: "dashboard",
                list: "/",
                meta: {
                  label: "Dashboard",
                  hide: true,
                },
              },
              {
                name: "orders",
                list: "/orders",
                show: "/orders/:id",
                meta: {
                  icon: <ShoppingBagOutlinedIcon />,
                },
              },
              {
                name: "data",
                list: "/data",
                show: "/data/:id",
                create: "/data/new",
                meta: {
                  dataProviderName: "dflowp",
                  icon: <StorageOutlinedIcon />,
                },
              },
            ]}
          >
            <Routes>
              <Route
                element={
                  <Authenticated
                    key="authenticated-routes"
                    fallback={<CatchAllNavigate to="/login" />}
                  >
                    <ThemedLayout
                      Header={Header}
                      Title={Title}
                      Sider={MinimalSider}
                    >
                      <Box
                        sx={{
                          maxWidth: "1200px",
                          marginLeft: "auto",
                          marginRight: "auto",
                        }}
                      >
                        <Outlet />
                      </Box>
                    </ThemedLayout>
                  </Authenticated>
                }
              >
                <Route index element={<DashboardPage />} />

                <Route path="/orders">
                  <Route index element={<OrderList />} />
                  <Route path=":id" element={<OrderShow />} />
                </Route>

                <Route path="/data">
                  <Route index element={<DataList />} />
                  <Route path="new" element={<DataCreate />} />
                  <Route path=":id" element={<DataShow />} />
                </Route>
              </Route>

              <Route
                element={
                  <Authenticated key="auth-pages" fallback={<Outlet />}>
                    <NavigateToResource resource="dashboard" />
                  </Authenticated>
                }
              >
                <Route
                  path="/login"
                  element={
                    <AuthPage
                      type="login"
                      registerLink={false}
                      forgotPasswordLink={false}
                      formProps={{
                        defaultValues: {
                          email: "demo@refine.dev",
                          password: "demodemo",
                        },
                      }}
                    />
                  }
                />
              </Route>

              <Route
                element={
                  <Authenticated key="catch-all">
                    <ThemedLayout
                      Header={Header}
                      Title={Title}
                      Sider={MinimalSider}
                    >
                      <Outlet />
                    </ThemedLayout>
                  </Authenticated>
                }
              >
                <Route path="*" element={<ErrorComponent />} />
              </Route>
            </Routes>
            <UnsavedChangesNotifier />
            <DocumentTitleHandler />
          </Refine>
        </RefineSnackbarProvider>
      </ColorModeContextProvider>
    </BrowserRouter>
  );
};

export default App;
