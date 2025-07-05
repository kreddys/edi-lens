import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import keycloak from "./keycloak";

const root = ReactDOM.createRoot(document.getElementById("root")!);

// Display a loading message while Keycloak is initializing
root.render(
  <React.StrictMode>
    <div>Loading...</div>
  </React.StrictMode>
);

keycloak.init({ onLoad: 'login-required' })
  .then((authenticated) => {
    if (authenticated) {
      // If authenticated, render the main application
      root.render(
        <React.StrictMode>
          <App />
        </React.StrictMode>
      );
    } else {
      // This part should ideally not be reached because of 'login-required',
      // but it's good practice to handle it.
      root.render(
        <React.StrictMode>
          <div>Unable to authenticate. Please try again.</div>
        </React.StrictMode>
      );
    }
  })
  .catch((error) => {
    console.error("Keycloak initialization failed:", error);
    root.render(
      <React.StrictMode>
        <div>Error initializing Keycloak. See console for details.</div>
      </React.StrictMode>
    );
  });