/**
 * XenoSys Gateway - Plugin System
 * Extensible plugin architecture
 */

import { readFileSync, existsSync } from 'fs';
import { parse as parseYaml } from 'yaml';
import { v4 as uuid } from 'uuid';
import { Plugin, PluginSchema, PluginCapabilitySchema } from '../gateway/types.js';

// ============================================================================
// Plugin Types
// ============================================================================

interface PluginInstance {
  id: string;
  plugin: Plugin;
  hooks: Map<string, Array<{ priority: number; handler: (ctx: unknown) => Promise<unknown> }>>;
  state: Map<string, unknown>;
  api: PluginAPI;
  initialize(): Promise<void>;
  shutdown(): Promise<void>;
}

interface PluginAPI {
  logger: {
    info: (msg: string, data?: Record<string, unknown>) => void;
    warn: (msg: string, data?: Record<string, unknown>) => void;
    error: (msg: string, data?: Record<string, unknown>) => void;
  };
  config: {
    get: (key: string, defaultValue?: unknown) => unknown;
    set: (key: string, value: unknown) => void;
  };
  storage: {
    get: (key: string) => unknown;
    set: (key: string, value: unknown) => void;
    delete: (key: string) => void;
    list: () => string[];
  };
  events: {
    on: (event: string, handler: (data: unknown) => void) => void;
    off: (event: string, handler: (data: unknown) => void) => void;
    emit: (event: string, data: unknown) => void;
  };
  tools: {
    register: (name: string, schema: Record<string, unknown>, handler: (args: unknown) => Promise<string>) => void;
    unregister: (name: string) => void;
  };
}

interface PluginManifest {
  id: string;
  name: string;
  version: string;
  description?: string;
  main: string;
  capabilities: string[];
  dependencies?: string[];
  config?: Record<string, unknown>;
}

// ============================================================================
// Plugin Manager
// ============================================================================

export class PluginManager {
  private static instance: PluginManager;
  private plugins: Map<string, PluginInstance> = new Map();
  private pluginDir: string;
  private loaded = false;

  private constructor(pluginDir?: string) {
    this.pluginDir = pluginDir ?? process.env['PLUGIN_DIR'] ?? './plugins';
  }

  static getInstance(pluginDir?: string): PluginManager {
    if (!PluginManager.instance) {
      PluginManager.instance = new PluginManager(pluginDir);
    }
    return PluginManager.instance;
  }

  /**
   * Load all plugins from directory
   */
  async loadPlugins(): Promise<void> {
    if (this.loaded) return;

    const manifestPath = `${this.pluginDir}/plugins.yaml`;

    if (!existsSync(manifestPath)) {
      console.log('No plugins manifest found');
      return;
    }

    try {
      const content = readFileSync(manifestPath, 'utf-8');
      const manifest = parseYaml(content) as { plugins: PluginManifest[] };

      for (const pluginManifest of manifest.plugins ?? []) {
        try {
          await this.loadPlugin(pluginManifest);
        } catch (error) {
          console.error(`Failed to load plugin ${pluginManifest.id}:`, error);
        }
      }
    } catch (error) {
      console.error('Failed to load plugin manifest:', error);
    }

    this.loaded = true;
  }

  /**
   * Load a single plugin
   */
  async loadPlugin(manifest: PluginManifest): Promise<void> {
    if (this.plugins.has(manifest.id)) {
      console.warn(`Plugin ${manifest.id} already loaded`);
      return;
    }

    // Validate manifest
    const parsed = PluginSchema.safeParse({
      id: manifest.id,
      name: manifest.name,
      version: manifest.version,
      description: manifest.description,
      capabilities: manifest.capabilities,
      dependencies: manifest.dependencies,
      config: manifest.config,
    });

    if (!parsed.success) {
      throw new Error(`Invalid plugin manifest: ${parsed.error.message}`);
    }

    const plugin = parsed.data;

    // Check dependencies
    for (const depId of manifest.dependencies ?? []) {
      if (!this.plugins.has(depId)) {
        throw new Error(`Missing dependency: ${depId}`);
      }
    }

    // Create plugin API
    const api = this.createPluginAPI(manifest.id);

    // Create plugin instance
    const instance: PluginInstance = {
      id: manifest.id,
      plugin,
      hooks: new Map(),
      state: new Map(),
      api,
      initialize: async () => {
        // Dynamic import of plugin module
        const pluginPath = `${this.pluginDir}/${manifest.id}/${manifest.main}`;
        const mod = await import(pluginPath);
        return mod.initialize?.(api) ?? Promise.resolve();
      },
      shutdown: async () => {
        const pluginPath = `${this.pluginDir}/${manifest.id}/${manifest.main}`;
        const mod = await import(pluginPath);
        return mod.shutdown?.() ?? Promise.resolve();
      },
    };

    // Initialize plugin
    await instance.initialize();

    // Register hooks
    await this.registerPluginHooks(instance, manifest.id);

    this.plugins.set(manifest.id, instance);
    console.log(`Plugin loaded: ${manifest.id} v${manifest.version}`);
  }

  /**
   * Create plugin API
   */
  private createPluginAPI(pluginId: string): PluginAPI {
    return {
      logger: {
        info: (msg, data) => console.log(`[${pluginId}]`, msg, data ?? {}),
        warn: (msg, data) => console.warn(`[${pluginId}]`, msg, data ?? {}),
        error: (msg, data) => console.error(`[${pluginId}]`, msg, data ?? {}),
      },
      config: {
        get: (key, defaultValue) => {
          const instance = this.plugins.get(pluginId);
          return instance?.state.get(`config.${key}`) ?? defaultValue;
        },
        set: (key, value) => {
          const instance = this.plugins.get(pluginId);
          instance?.state.set(`config.${key}`, value);
        },
      },
      storage: {
        get: (key) => this.plugins.get(pluginId)?.state.get(`storage.${key}`),
        set: (key, value) => this.plugins.get(pluginId)?.state.set(`storage.${key}`, value),
        delete: (key) => this.plugins.get(pluginId)?.state.delete(`storage.${key}`),
        list: () => {
          const instance = this.plugins.get(pluginId);
          if (!instance) return [];
          return Array.from(instance.state.keys())
            .filter(k => k.startsWith('storage.'))
            .map(k => k.replace('storage.', ''));
        },
      },
      events: {
        on: (event, handler) => {
          const instance = this.plugins.get(pluginId);
          if (!instance) return;

          const key = `storage.event.${event}`;
          const handlers = (instance.state.get(key) as Array<(data: unknown) => void>) ?? [];
          handlers.push(handler);
          instance.state.set(key, handlers);
        },
        off: (event, handler) => {
          const instance = this.plugins.get(pluginId);
          if (!instance) return;

          const key = `storage.event.${event}`;
          const handlers = (instance.state.get(key) as Array<(data: unknown) => void>) ?? [];
          const idx = handlers.indexOf(handler);
          if (idx >= 0) handlers.splice(idx, 1);
          instance.state.set(key, handlers);
        },
        emit: (event, data) => {
          const instance = this.plugins.get(pluginId);
          if (!instance) return;

          const key = `storage.event.${event}`;
          const handlers = (instance.state.get(key) as Array<(d: unknown) => void>) ?? [];
          handlers.forEach(h => h(data));
        },
      },
      tools: {
        register: (name, schema, handler) => {
          // Tool registration would integrate with the tool registry
          console.log(`Plugin ${pluginId} registering tool: ${name}`);
        },
        unregister: (name) => {
          console.log(`Plugin ${pluginId} unregistering tool: ${name}`);
        },
      },
    };
  }

  /**
   * Register plugin hooks
   */
  private async registerPluginHooks(instance: PluginInstance, pluginId: string): Promise<void> {
    // Hooks are registered by the plugin via the api.events.on method
    // This method is called during plugin initialization
  }

  /**
   * Invoke hook handlers
   */
  async invokeHook(hookName: string, context: unknown): Promise<unknown> {
    let result = context;

    for (const instance of this.plugins.values()) {
      const key = `storage.event.${hookName}`;
      const handlers = (instance.state.get(key) as Array<(ctx: unknown) => Promise<unknown>>) ?? [];

      for (const handler of handlers) {
        try {
          result = await handler(result);
        } catch (error) {
          console.error(`Plugin ${instance.id} hook error:`, error);
        }
      }
    }

    return result;
  }

  /**
   * Get plugin instance
   */
  getPlugin(id: string): PluginInstance | undefined {
    return this.plugins.get(id);
  }

  /**
   * Get all plugins
   */
  getAllPlugins(): PluginInstance[] {
    return Array.from(this.plugins.values());
  }

  /**
   * Get plugins by capability
   */
  getPluginsByCapability(capability: string): PluginInstance[] {
    return Array.from(this.plugins.values())
      .filter(p => p.plugin.capabilities.includes(capability as Plugin['capabilities'][number]));
  }

  /**
   * Unload a plugin
   */
  async unloadPlugin(id: string): Promise<boolean> {
    const instance = this.plugins.get(id);
    if (!instance) return false;

    await instance.shutdown();
    this.plugins.delete(id);
    return true;
  }

  /**
   * Unload all plugins
   */
  async unloadAll(): Promise<void> {
    for (const [id] of this.plugins) {
      await this.unloadPlugin(id);
    }
    this.loaded = false;
  }
}
