// @vitest-environment node
import { describe, it, expect } from 'vitest';
import type { UserConfig } from 'vite';
import viteConfig from '../../vite.config';

describe('Vite Dev Proxy Configuration', () => {
  it('forwards /api without stripping the prefix', async () => {
    const configFn = viteConfig as UserConfig | ((env: { command: string; mode: string }) => UserConfig | Promise<UserConfig>);
    const resolvedConfig = typeof configFn === 'function'
      ? await configFn({ command: 'serve', mode: 'development' })
      : await configFn;

    const proxy = resolvedConfig.server?.proxy;
    expect(proxy).toBeDefined();
    if (!proxy) throw new Error('Proxy is undefined');

    const apiProxy = proxy['/api'];
    expect(apiProxy).toBeDefined();

    if (typeof apiProxy === 'object' && !Array.isArray(apiProxy)) {
      expect(apiProxy.changeOrigin).toBe(true);
      expect('rewrite' in apiProxy).toBe(false);
    }
  });
});
