// src/vite-env.d.ts
/// <reference types="vite/client" />

// Add this module declaration for raw XML imports
declare module '*.xml?raw' {
    const content: string;
    export default content;
}

// Ensure this one exists for .edi files
declare module '*.edi?raw' {
    const content: string;
    export default content;
}

// Add for .txt if you use that extension
declare module '*.txt?raw' {
    const content: string;
    export default content;
}