import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

import { ErrorComponent } from "@refinedev/antd";
import "@refinedev/antd/dist/reset.css";

import {
  DesktopOutlined,
  FileOutlined,
  HighlightOutlined,
  HomeOutlined,
  PrinterOutlined,
  ProjectOutlined,
  QuestionOutlined,
  TableOutlined,
  ToolOutlined,
  UserOutlined,
} from "@ant-design/icons";
import loadable from "@loadable/component";
import routerBindings, { DocumentTitleHandler, UnsavedChangesNotifier } from "@refinedev/react-router";
import { ConfigProvider } from "antd";
import { Locale } from "antd/es/locale";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Outlet, Route, Routes } from "react-router";
import dataProvider from "./components/dataProvider";
import { Favicon } from "./components/favicon";
import { SpoolmanLayout } from "./components/layout";
import liveProvider from "./components/liveProvider";
import SpoolmanNotificationProvider from "./components/notificationProvider";
import { ColorModeContextProvider } from "./contexts/color-mode";
import { languages } from "./i18n";
import { getAPIURL, getBasePath } from "./utils/url";

interface ResourcePageProps {
  resource: "spools" | "filaments" | "vendors";
  page: "list" | "create" | "edit" | "show";
  mode?: "create" | "clone";
}

const LoadableResourcePage = loadable(
  (props: ResourcePageProps) => import(`./pages/${props.resource}/${props.page}.tsx`),
  {
    fallback: <div>Page is Loading...</div>,
    cacheKey: (props: ResourcePageProps) => `${props.resource}-${props.page}-${props.mode ?? ""}`,
  },
);

interface LoadablePageProps {
  name: string;
}

const LoadablePage = loadable((props: LoadablePageProps) => import(`./pages/${props.name}/index.tsx`), {
  fallback: <div>Page is Loading...</div>,
  cacheKey: (props: LoadablePageProps) => `page-${props.name}`,
});

interface LoadableSimplePageProps {
  page: "list" | "create" | "edit";
  mode?: "create" | "clone";
}

const LoadableProjectPage = loadable(
  (props: LoadableSimplePageProps) => import(`./pages/projects/${props.page}.tsx`),
  {
    fallback: <div>Page is Loading...</div>,
    cacheKey: (props: LoadableSimplePageProps) => `project-${props.page}-${props.mode ?? ""}`,
  },
);

const LoadablePlatePage = loadable(
  (props: LoadableSimplePageProps) => import(`./pages/plates/${props.page}.tsx`),
  {
    fallback: <div>Page is Loading...</div>,
    cacheKey: (props: LoadableSimplePageProps) => `plate-${props.page}-${props.mode ?? ""}`,
  },
);

const LoadablePrintJobPage = loadable(
  (props: LoadableSimplePageProps) => import(`./pages/print_jobs/${props.page}.tsx`),
  {
    fallback: <div>Page is Loading...</div>,
    cacheKey: (props: LoadableSimplePageProps) => `print_job-${props.page}-${props.mode ?? ""}`,
  },
);

const LoadablePrinterPage = loadable(
  (props: LoadableSimplePageProps) => import(`./pages/printers/${props.page}.tsx`),
  {
    fallback: <div>Page is Loading...</div>,
    cacheKey: (props: LoadableSimplePageProps) => `printer-${props.page}-${props.mode ?? ""}`,
  },
);

function App() {
  const { t, i18n } = useTranslation();

  const i18nProvider = {
    translate: (key: string, params?: never) => t(key, params),
    changeLocale: (lang: string) => i18n.changeLanguage(lang),
    getLocale: () => i18n.language,
  };

  // Fetch the antd locale using dynamic imports
  const [antdLocale, setAntdLocale] = useState<Locale | undefined>();
  useEffect(() => {
    const fetchLocale = async () => {
      const locale = await import(
        `./../node_modules/antd/es/locale/${languages[i18n.language].fullCode.replace("-", "_")}.js`
      );
      setAntdLocale(locale.default);
    };
    fetchLocale().catch(console.error);
  }, [i18n.language]);

  if (!import.meta.env.VITE_APIURL) {
    return (
      <>
        <h1>Missing API URL</h1>
        <p>
          App was built without an API URL. Please set the VITE_APIURL environment variable to the URL of your Spoolman
          API.
        </p>
      </>
    );
  }

  return (
    <BrowserRouter basename={getBasePath() + "/"}>
      <RefineKbarProvider>
        <ColorModeContextProvider>
          <ConfigProvider locale={antdLocale}>
            <Refine
              dataProvider={dataProvider(getAPIURL())}
              notificationProvider={SpoolmanNotificationProvider}
              i18nProvider={i18nProvider}
              routerProvider={routerBindings}
              liveProvider={liveProvider(getAPIURL())}
              resources={[
                {
                  name: "home",
                  list: "/",
                  meta: {
                    canDelete: false,
                    icon: <HomeOutlined />,
                  },
                },
                {
                  name: "Spool Management",
                  meta: {
                    icon: <FileOutlined />,
                    label: "Spool Management",
                  },
                },
                {
                  name: "spool",
                  list: "/spool",
                  create: "/spool/create",
                  clone: "/spool/clone/:id",
                  edit: "/spool/edit/:id",
                  show: "/spool/show/:id",
                  meta: {
                    canDelete: true,
                    icon: <FileOutlined />,
                    parent: "Spool Management",
                  },
                },
                {
                  name: "filament",
                  list: "/filament",
                  create: "/filament/create",
                  clone: "/filament/clone/:id",
                  edit: "/filament/edit/:id",
                  show: "/filament/show/:id",
                  meta: {
                    canDelete: true,
                    icon: <HighlightOutlined />,
                    parent: "Spool Management",
                  },
                },
                {
                  name: "vendor",
                  list: "/vendor",
                  create: "/vendor/create",
                  clone: "/vendor/clone/:id",
                  edit: "/vendor/edit/:id",
                  show: "/vendor/show/:id",
                  meta: {
                    canDelete: true,
                    icon: <UserOutlined />,
                    parent: "Spool Management",
                  },
                },
                {
                  name: "locations",
                  list: "/locations",
                  meta: {
                    canDelete: false,
                    icon: <TableOutlined />,
                    parent: "Spool Management",
                  },
                },
                {
                  name: "Print Management",
                  meta: {
                    icon: <PrinterOutlined />,
                    label: "Print Management",
                  },
                },
                {
                  name: "project",
                  list: "/project",
                  create: "/project/create",
                  clone: "/project/clone/:id",
                  edit: "/project/edit/:id",
                  meta: {
                    canDelete: true,
                    icon: <ProjectOutlined />,
                    parent: "Print Management",
                  },
                },
                {
                  name: "plate",
                  list: "/plate",
                  create: "/plate/create",
                  clone: "/plate/clone/:id",
                  edit: "/plate/edit/:id",
                  meta: {
                    canDelete: true,
                    icon: <FileOutlined />,
                    parent: "Print Management",
                  },
                },
                {
                  name: "print_job",
                  list: "/print_job",
                  create: "/print_job/create",
                  edit: "/print_job/edit/:id",
                  meta: {
                    canDelete: true,
                    icon: <PrinterOutlined />,
                    parent: "Print Management",
                  },
                },
                {
                  name: "printer",
                  list: "/printer",
                  create: "/printer/create",
                  clone: "/printer/clone/:id",
                  edit: "/printer/edit/:id",
                  meta: {
                    canDelete: true,
                    icon: <DesktopOutlined />,
                    parent: "Print Management",
                  },
                },
                {
                  name: "settings",
                  list: "/settings",
                  meta: {
                    canDelete: false,
                    icon: <ToolOutlined />,
                  },
                },
                {
                  name: "help",
                  list: "/help",
                  meta: {
                    canDelete: false,
                    icon: <QuestionOutlined />,
                  },
                },
              ]}
              options={{
                syncWithLocation: true,
                warnWhenUnsavedChanges: true,
                disableTelemetry: true,
              }}
            >
              <Routes>
                <Route
                  element={
                    <SpoolmanLayout>
                      <Outlet />
                    </SpoolmanLayout>
                  }
                >
                  <Route index element={<LoadablePage name="home" />} />
                  <Route path="/spool">
                    <Route index element={<LoadableResourcePage resource="spools" page="list" />} />
                    <Route
                      path="create"
                      element={<LoadableResourcePage resource="spools" page="create" mode="create" />}
                    />
                    <Route
                      path="clone/:id"
                      element={<LoadableResourcePage resource="spools" page="create" mode="clone" />}
                    />
                    <Route path="edit/:id" element={<LoadableResourcePage resource="spools" page="edit" />} />
                    <Route path="show/:id" element={<LoadableResourcePage resource="spools" page="show" />} />
                    <Route path="print" element={<LoadablePage name="printing" />} />
                  </Route>
                  <Route path="/filament">
                    <Route index element={<LoadableResourcePage resource="filaments" page="list" />} />
                    <Route
                      path="create"
                      element={<LoadableResourcePage resource="filaments" page="create" mode="create" />}
                    />
                    <Route
                      path="clone/:id"
                      element={<LoadableResourcePage resource="filaments" page="create" mode="clone" />}
                    />
                    <Route path="edit/:id" element={<LoadableResourcePage resource="filaments" page="edit" />} />
                    <Route path="show/:id" element={<LoadableResourcePage resource="filaments" page="show" />} />
                  </Route>
                  <Route path="/vendor">
                    <Route index element={<LoadableResourcePage resource="vendors" page="list" />} />
                    <Route
                      path="create"
                      element={<LoadableResourcePage resource="vendors" page="create" mode="create" />}
                    />
                    <Route
                      path="clone/:id"
                      element={<LoadableResourcePage resource="vendors" page="create" mode="clone" />}
                    />
                    <Route path="edit/:id" element={<LoadableResourcePage resource="vendors" page="edit" />} />
                    <Route path="show/:id" element={<LoadableResourcePage resource="vendors" page="show" />} />
                  </Route>
                  <Route path="/project">
                    <Route index element={<LoadableProjectPage page="list" />} />
                    <Route path="create" element={<LoadableProjectPage page="create" mode="create" />} />
                    <Route path="clone/:id" element={<LoadableProjectPage page="create" mode="clone" />} />
                    <Route path="edit/:id" element={<LoadableProjectPage page="edit" />} />
                  </Route>
                  <Route path="/plate">
                    <Route index element={<LoadablePlatePage page="list" />} />
                    <Route path="create" element={<LoadablePlatePage page="create" mode="create" />} />
                    <Route path="clone/:id" element={<LoadablePlatePage page="create" mode="clone" />} />
                    <Route path="edit/:id" element={<LoadablePlatePage page="edit" />} />
                  </Route>
                  <Route path="/print_job">
                    <Route index element={<LoadablePrintJobPage page="list" />} />
                    <Route path="create" element={<LoadablePrintJobPage page="create" mode="create" />} />
                    <Route path="edit/:id" element={<LoadablePrintJobPage page="edit" />} />
                  </Route>
                  <Route path="/printer">
                    <Route index element={<LoadablePrinterPage page="list" />} />
                    <Route path="create" element={<LoadablePrinterPage page="create" mode="create" />} />
                    <Route path="clone/:id" element={<LoadablePrinterPage page="create" mode="clone" />} />
                    <Route path="edit/:id" element={<LoadablePrinterPage page="edit" />} />
                  </Route>
                  <Route path="/settings/*" element={<LoadablePage name="settings" />} />
                  <Route path="/help" element={<LoadablePage name="help" />} />
                  <Route path="/locations" element={<LoadablePage name="locations" />} />
                  <Route path="*" element={<ErrorComponent />} />
                </Route>
              </Routes>

              <RefineKbar />
              <UnsavedChangesNotifier />
              <DocumentTitleHandler />
              <ReactQueryDevtools />
              <Favicon url={getBasePath() + "/favicon.svg"} />
            </Refine>
          </ConfigProvider>
        </ColorModeContextProvider>
      </RefineKbarProvider>
    </BrowserRouter>
  );
}

export default App;
