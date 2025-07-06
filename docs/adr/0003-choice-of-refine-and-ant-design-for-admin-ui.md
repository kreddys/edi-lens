# ADR 0003: Choice of Refine.js and Ant Design for Admin UI

-   **Status**: Accepted
-   **Date**: 2025-07-06

## Context

The project requires an administrative user interface for managing complex data entities like Trading Partners. The UI needs to be developed quickly, be easy to maintain, and have a professional, enterprise-grade look and feel.

## Decision

We have decided to build the Admin UI using the **Refine.js** framework with the **Ant Design** component library.

## Rationale

1.  **Rapid Development with Refine.js**: Refine is a React-based framework specifically designed for building data-intensive applications like admin panels and internal tools.
    -   **Headless by Design**: Its core hooks (`useTable`, `useForm`) are decoupled from the UI, providing business logic for data fetching, state management, and routing.
    -   **Built-in Providers**: It offers a provider-based system for data, authentication, access control, and notifications, which drastically reduces boilerplate code.
    -   **Strong Community and Documentation**: Refine is a well-supported project with excellent documentation and examples.

2.  **Professional UI with Ant Design**: Ant Design is a comprehensive, high-quality component library with a mature design system.
    -   **Rich Component Set**: It provides a vast array of components needed for enterprise applications, including powerful tables, forms, modals, and data display elements.
    -   **Theming and Customization**: Ant Design's theming system is robust and allows for deep customization, enabling us to create a unique and polished look for the application.
    -   **Seamless Refine Integration**: The `@refinedev/antd` package provides a seamless bridge between Refine's hooks and Ant Design's components, making them work together effortlessly.

3.  **Alternative Considered**: We initially used Material-UI. While functional, Ant Design was chosen for its more data-dense and enterprise-focused aesthetic, which better suits the goals of the EDI Lens application.

## Consequences

-   **Learning Curve**: Developers new to the project will need to familiarize themselves with the conventions and hooks of the Refine.js framework.
-   **Dependency**: The project is dependent on the Refine.js ecosystem. However, because of its headless nature, migrating away from the Ant Design UI layer to another (like Material-UI) remains feasible if ever required.