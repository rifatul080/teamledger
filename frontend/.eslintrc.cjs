module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module" },
  settings: { react: { version: "18.3" } },
  ignorePatterns: ["dist", "node_modules", "coverage"],
  rules: {
    "react/react-in-jsx-scope": "off",
    // Prose in JSX (apostrophes, quotes in UI copy) — flagging it is noise.
    "react/no-unescaped-entities": "off",
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
  },
};
