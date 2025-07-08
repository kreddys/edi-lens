import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
import { ErrorComponent, useNotificationProvider } from "@refinedev/antd";
import "@refinedev/antd/dist/reset.css";

import routerBindings, { NavigateToResource, UnsavedChangesNotifier } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout";
import { dataProvider, authProvider, accessControlProvider, ThemeProvider } from "./providers";

import { TradingPartnerList, TradingPartnerCreate, TradingPartnerEdit, TradingPartnerShow } from "./pages/tradingPartners";
import { SchemaEditorList } from "./pages/schemaEditor/list"; // IMPORT THE NEW PAGE

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
                  name: "trading-partners",
                  list: "/trading-partners",
                  create: "/trading-partners/create",
                  edit: "/trading-partners/edit/:id",
                  show: "/trading-partners/show/:id",
                  meta: { label: "Trading Partners" },
                },
                // --- THIS IS THE FIX ---
                // Add the 'list' and 'meta.label' properties to make the resource
                // appear in the navigation menu.
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
                  <Route index element={<NavigateToResource resource="trading-partners" />} />
                  <Route path="/trading-partners">
                    <Route index element={<TradingPartnerList />} />
                    <Route path="create" element={<TradingPartnerCreate />} />
                    <Route path="edit/:id" element={<TradingPartnerEdit />} />
                    <Route path="show/:id" element={<TradingPartnerShow />} />
                  </Route>
                  {/* ADD THE ROUTE FOR THE NEW PAGE */}
                  <Route path="/schema-editor" element={<SchemaEditorList />} />
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