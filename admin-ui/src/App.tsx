import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
import { ErrorComponent } from "@refinedev/mui";
// --- THIS IS THE FIX ---
import routerBindings, { NavigateToResource, UnsavedChangesNotifier } from "@refinedev/react-router-v6";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";
import { CssBaseline, GlobalStyles } from "@mui/material";

import { dataProvider } from "./dataProvider";
import { authProvider } from "./authProvider";
import { Layout } from "./components/layout";
import { TradingPartnerList, TradingPartnerCreate } from "./pages/tradingPartners";

function App() {
  return (
    <BrowserRouter>
      <RefineKbarProvider>
        <CssBaseline />
        <GlobalStyles styles={{ html: { WebkitFontSmoothing: "auto" } }} />
          <Refine
            dataProvider={dataProvider}
            routerProvider={routerBindings}
            authProvider={authProvider}
            resources={[
              {
                name: "trading-partners",
                list: "/trading-partners",
                create: "/trading-partners/create",
                meta: { label: "Trading Partners" },
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
      </RefineKbarProvider>
    </BrowserRouter>
  );
}
export default App;