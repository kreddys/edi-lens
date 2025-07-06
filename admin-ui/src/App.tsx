import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
import {
    ErrorComponent,
    useNotificationProvider,
    RefineThemes,
} from "@refinedev/antd";
import { App as AntdApp, ConfigProvider } from "antd";
import "@refinedev/antd/dist/reset.css";

import routerBindings, { NavigateToResource, UnsavedChangesNotifier } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";

import { dataProvider } from "./dataProvider";
import { authProvider } from "./authProvider";
// --- THIS IS THE FIX ---
// Import the new access control provider
import { accessControlProvider } from "./accessControlProvider";
import { Layout } from "./components/layout";
import { TradingPartnerList, TradingPartnerCreate } from "./pages/tradingPartners";

function App() {
  return (
    <BrowserRouter>
      <RefineKbarProvider>
        <ConfigProvider theme={RefineThemes.Blue}>
          <AntdApp>
            <Refine
              dataProvider={dataProvider}
              routerProvider={routerBindings}
              authProvider={authProvider}
              notificationProvider={useNotificationProvider}
              // --- THIS IS THE FIX ---
              // Add the access control provider to the Refine component
              accessControlProvider={accessControlProvider}
              resources={[
                {
                  name: "trading-partners",
                  list: "/trading-partners",
                  create: "/trading-partners/create",
                  meta: { 
                    label: "Trading Partners",
                    // This tells Refine which permission is needed to even see this in the menu
                    canDelete: true, // Example, not used yet but good practice
                  },
                },
              ]}
              options={{
                syncWithLocation: true,
                warnWhenUnsavedChanges: true,
              }}
            >
              <Routes>
                <Route element={<Layout><Outlet /></Layout>}>
                  <Route index element={<NavigateToResource resource="trading-partners" />} />
                  <Route path="/trading-partners">
                    <Route index element={<TradingPartnerList />} />
                    <Route path="create" element={<TradingPartnerCreate />} />
                  </Route>
                  <Route path="*" element={<ErrorComponent />} />
                </Route>
              </Routes>
              <RefineKbar />
              <UnsavedChangesNotifier />
            </Refine>
          </AntdApp>
        </ConfigProvider>
      </RefineKbarProvider>
    </BrowserRouter>
  );
}
export default App;