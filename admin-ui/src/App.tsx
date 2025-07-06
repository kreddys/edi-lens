import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
import { ErrorComponent, useNotificationProvider } from "@refinedev/antd";
import "@refinedev/antd/dist/reset.css";

import routerBindings, { NavigateToResource, UnsavedChangesNotifier } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout";
import { dataProvider, authProvider, accessControlProvider, ThemeProvider } from "./providers";

// --- THIS IS THE FIX ---
// Import each component directly from its file path.
import { TradingPartnerList } from "./pages/tradingPartners/list";
import { TradingPartnerCreate } from "./pages/tradingPartners/create";
import { TradingPartnerEdit } from "./pages/tradingPartners/edit";
import { TradingPartnerShow } from "./pages/tradingPartners/show";

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