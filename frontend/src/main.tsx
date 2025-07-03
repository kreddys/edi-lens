import React from 'react';
import ReactDOM from 'react-dom/client';
// Import base Tailwind styles and Ace editor overrides from index.css
import './index.css';
// Ensure App component is imported correctly
import App from './App.tsx';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);