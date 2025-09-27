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

// Standard Refine pages
import { FlowList } from "./pages/flows/FlowList";
import { FlowCreate } from "./pages/flows/FlowCreate";
import { FlowShow } from "./pages/flows/FlowShow";
import { FlowEdit } from "./pages/flows/FlowEdit";

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
                  create: "/flows/create", 
                  edit: "/flows/:id/edit",
                  show: "/flows/:id",
                  meta: { 
                    label: "Flows"
                  },
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
                  <Route path="/flows" element={<FlowList />} />
                  <Route path="/flows/create" element={<FlowCreate />} />
                  <Route path="/flows/:id" element={<FlowShow />} />
                  <Route path="/flows/:id/edit" element={<FlowEdit />} />
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