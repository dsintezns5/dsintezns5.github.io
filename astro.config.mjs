// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  site: 'https://dsintezns5.github.io',
  trailingSlash: 'ignore',
  // Локальный preview/dev-сервер: разрешить внешние хосты (песочница, LAN)
  server: {
    allowedHosts: true,
  },
});
