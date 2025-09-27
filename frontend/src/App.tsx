import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
import { ErrorComponent, useNotificationProvider } from "@refinedev/antd";
import { App as AntdApp } from "antd";
import "@refinedev/antd/dist/reset.css";

import routerBindings, { NavigateToResource, UnsavedChangesNotifier } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout";
import { dataProvider, ThemeProvider } from "./providers";

import { SchemaEditorList } from "./pages/schemaEditor/SchemaEditorList";

import { FlowManagement } from "./pages/flows";

function App() {
  return (
    <BrowserRouter>
      <RefineKbarProvider>
        <ThemeProvider>
          <AntdApp>
            <Refine
              dataProvider={dataProvider}
              routerProvider={routerBindings}
              notificationProvider={useNotificationProvider}
              resources={[
                {
                  name: "flows",
                  list: "/flows",
                  meta: { label: "Flows" },
                },
                {
                  name: "schemas",
                  list: "/schema-editor",
                  meta: {
                    label: "Schema Editor",
                    canDelete: false
                  }
                }
              ]}
              options={{ syncWithLocation: true, warnWhenUnsavedChanges: true }}
            >
              <Routes>
                <Route element={<Layout><Outlet /></Layout>}>
                  <Route index element={<NavigateToResource resource="flows" />} />
                  <Route path="/flows" element={<FlowManagement />} />
                  <Route path="/schema-editor" element={<SchemaEditorList />} />
                  <Route path="*" element={<ErrorComponent />} />
                </Route>
              </Routes>
              <RefineKbar />
              <UnsavedChangesNotifier />
            </Refine>
          </AntdApp>
        </ThemeProvider>
      </RefineKbarProvider>
    </BrowserRouter>
  );
}
export default App;