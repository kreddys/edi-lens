module.exports = {
  presets: [
    ['@babel/preset-env', { targets: { node: 'current' } }],
    ['@babel/preset-react', { runtime: 'automatic' }],
    ['@babel/preset-typescript', {
      allowDeclareFields: true,
      allowNamespaces: true,
      allExtensions: true,
      isTSX: true
    }],
  ],
  plugins: [
    // Transform import.meta to a global variable for Jest
    function() {
      return {
        visitor: {
          MetaProperty(path) {
            if (path.node.meta.name === 'import' && path.node.property.name === 'meta') {
              path.replaceWithSourceString('globalThis.import.meta');
            }
          }
        }
      };
    }
  ],
};