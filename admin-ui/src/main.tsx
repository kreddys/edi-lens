import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { keycloak } from "./utils"; // Updated import path

const root = ReactDOM.createRoot(document.getElementById("root")!);

root.render(<React.StrictMode><div>Loading...</div></React.StrictMode>);

keycloak.init({ onLoad: 'login-required' }).then((authenticated) => {
    if (authenticated) {
        root.render(<React.StrictMode><App /></React.StrictMode>);
    } else {
        root.render(<React.StrictMode><div>Unable to authenticate.</div></React.StrictMode>);
    }
}).catch((error) => {
    console.error("Keycloak initialization failed:", error);
    root.render(<React.StrictMode><div>Error initializing Keycloak.</div></React.StrictMode>);
});