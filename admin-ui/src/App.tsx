import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
// --- FIX: Removed unused 'Divider' ---
import { ErrorComponent, useNotificationProvider } from "@refinedev/antd";
import "@refinedev/antd/dist/reset.css";

import routerBindings, { NavigateToResource, UnsavedChangesNotifier } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout";
import { dataProvider, authProvider, accessControlProvider, ThemeProvider } from "./providers";

import { SchemaEditorList } from "./pages/schemaEditor/SchemaEditorList";
import { Validation, ProcessingHistory } from "./pages/validation";
import { 
  WorkflowTemplateList,
  WorkflowTemplateCreate,
  WorkflowTemplateEdit,
  WorkflowTemplateShow
} from "./pages/workflowTemplates";
import { 
  WorkflowList,
  WorkflowCreate,
  WorkflowEdit,
  WorkflowShow
} from "./pages/workflows";

function App() {
  return (
    <BrowserRouter>
      <RefineKbarProvider>
        <ThemeProvider>
            <Refine
              dataProvider={dataProvider}
              routerProvider={routerBindings}
              authProvider={authProvider}
              notificationProvider={useNotificationProvider}
              accessControlProvider={accessControlProvider}
              resources={[
                {
                  name: "workflow-templates",
                  list: "/workflow-templates",
                  create: "/workflow-templates/create",
                  edit: "/workflow-templates/edit/:id",
                  show: "/workflow-templates/show/:id",
                  meta: { label: "Workflow Templates" },
                },
                {
                  name: "workflows",
                  list: "/workflows",
                  create: "/workflows/create",
                  edit: "/workflows/edit/:id",
                  show: "/workflows/show/:id",
                  meta: { label: "Workflows" },
                },
                {
                    name: "schemas",
                    list: "/schema-editor",
                    meta: { 
                      label: "Schema Editor",
                      canDelete: false 
                    }
                },
                {
                  name: "processing-history",
                  list: "/processing-history",
                  meta: { label: "Processing History" },
                },
                {
                  name: "validation",
                  list: "/validation",
                  meta: { label: "Validation" },
                }              
              ]}
              options={{ syncWithLocation: true, warnWhenUnsavedChanges: true }}
            >
              <Routes>
                <Route element={<Layout><Outlet /></Layout>}>
                  <Route index element={<NavigateToResource resource="workflow-templates" />} />
                  <Route path="/workflow-templates">
                    <Route index element={<WorkflowTemplateList />} />
                    <Route path="create" element={<WorkflowTemplateCreate />} />
                    <Route path="edit/:id" element={<WorkflowTemplateEdit />} />
                    <Route path="show/:id" element={<WorkflowTemplateShow />} />
                  </Route>
                  <Route path="/workflows">
                    <Route index element={<WorkflowList />} />
                    <Route path="create" element={<WorkflowCreate />} />
                    <Route path="edit/:id" element={<WorkflowEdit />} />
                    <Route path="show/:id" element={<WorkflowShow />} />
                  </Route>
                  <Route path="/schema-editor" element={<SchemaEditorList />} />
                  <Route path="/processing-history" element={<ProcessingHistory />} />
                  <Route path="/validation" element={<Validation />} />
                  <Route path="*" element={<ErrorComponent />} />
                </Route>
              </Routes>
              <RefineKbar />
              <UnsavedChangesNotifier />
            </Refine>
        </ThemeProvider>
      </RefineKbarProvider>
    </BrowserRouter>
  );
}
export default App;