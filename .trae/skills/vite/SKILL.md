---
name: vite
description: "Guidance for Vite using the official Guide, Config Reference, and Plugins pages. Use when the user needs Vite setup, configuration, or plugin selection details."
license: Apache License 2.0
---

## When to use this skill

Use this skill whenever the user wants to:
- Follow Vite Guide topics from getting started to performance
- Configure Vite using the official config reference
- Select or understand Vite plugins from the official plugins page
- Use Vite CLI, HMR API, or JavaScript API
- Handle SSR, backend integration, or deployment scenarios in Vite

## How to use this skill

1. **Identify the topic** from the user request.
2. **Open the matching guide example** file in `examples/guide/`.
3. **If configuration is needed**, open the matching file in `examples/config/`.
4. **If plugin selection is needed**, open `examples/plugins.md`.
5. **Follow official docs verbatim** and keep output consistent with the referenced page.
6. **Validate**: Run `npm run build` to verify config changes compile; `npm run preview` to test production output.

### Inline Quick Start

```bash
# Create a new Vite project
npm create vite@latest my-app -- --template react-ts

# Install and run
cd my-app && npm install
npm run dev      # Dev server with HMR
npm run build    # Production build
npm run preview  # Preview production build
```

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: { vendor: ['react', 'react-dom'] },
      },
    },
  },
});
```

## Best Practices

- Use `defineConfig` for TypeScript type hints and autocomplete
- Configure proxy in `server.proxy` for API calls during development
- Use `build.rollupOptions.output.manualChunks` for vendor splitting
- Enable source maps in development; disable in production for smaller builds
- Use `import.meta.env` for environment variables (prefix with `VITE_`)

## Resources

- Guide: https://cn.vitejs.dev/guide/
- Config: https://cn.vitejs.dev/config/
- Plugins: https://cn.vitejs.dev/plugins/

## Keywords

Vite, build tool, dev server, HMR, config, plugins, SSR, CLI, dependency pre-bundling, assets