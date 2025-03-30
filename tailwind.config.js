/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors')

export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}", // Scan all relevant files in src
    ],
    theme: {
        extend: {
            // Define brand color palette based on slate and amber
            colors: {
                // Base Background and Text
                'brand-bg': colors.slate[900], // Dark background
                'brand-text-primary': colors.slate[200], // Light primary text
                'brand-text-secondary': colors.slate[400], // Muted secondary text
                'brand-text-muted': colors.slate[500], // Even more muted text

                // Surfaces and Borders
                'brand-surface': colors.slate[800], // Slightly lighter surface (inputs, cards)
                'brand-surface-alt': colors.slate[700], // Alternate surface (hover states, active lines)
                'brand-border': colors.slate[600], // Standard borders
                'brand-border-subtle': colors.slate[700], // Subtle borders (dividers)

                // Accent Color (e.g., for highlights, focus rings) - Used for Loops
                'brand-accent': colors.amber[500], // Primary accent
                'brand-accent-hover': colors.amber[600], // Accent hover

                // NEW: Segment ID Color
                'brand-segment-id': colors.cyan[400],
                'brand-segment-id-hover': colors.cyan[500], // Optional: Hover for segment ID if needed

                // Functional Colors (Errors, Warnings, Success)
                'brand-error': colors.red[500],
                'brand-error-bg': colors.red[900], // Background for error messages
                'brand-warning': colors.yellow[500],
                'brand-warning-bg': colors.yellow[900], // Background for warnings
                'brand-success': colors.green[500],
                'brand-success-bg': colors.green[900],

                // Code/Mono specific background
                'brand-code-bg': colors.slate[700],

                // Usage indicator colors (matched usage in ElementDisplay)
                'brand-usage-r': colors.red[400],   // Required
                'brand-usage-s': colors.sky[400], // Situational
                'brand-usage-n': colors.slate[500], // Not Used / Muted
            },
            fontFamily: {
                // Define sans and mono fonts if needed, otherwise defaults are fine
                // sans: ['Inter', 'sans-serif'],
                // mono: ['Fira Code', 'monospace'],
            },
        },
    },
    plugins: [],
}