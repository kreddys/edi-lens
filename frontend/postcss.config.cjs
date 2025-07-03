console.log("--- PostCSS config: Loading postcss.config.cjs ---"); // Add log

module.exports = {
  plugins: {
    tailwindcss: {}, // Use the v3 plugin name (from tailwindcss pkg)
    autoprefixer: {},
  }
}