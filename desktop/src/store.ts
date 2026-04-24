/**
 * XenoSys Secure Store - API Key Management
 * Uses Tauri Store plugin for secure, encrypted persistence
 * 
 * Stores keys in OS-specific location:
 * - Windows: %APPDATA%\com.xenosys.desktop\
 * - Mac: ~/Library/Application Support/com.xenosys.desktop/
 * - Linux: ~/.config/com.xenosys.desktop/
 */

import { Store } from '@tauri-apps/plugin-store';

// Create persistent store instance
const store = new Store('.settings.dat');

/**
 * Save API key securely
 * @param keyName - Key identifier (e.g., 'openai_api_key', 'cloudflare_token')
 * @param value - API key value
 */
export const saveApiKey = async (keyName: string, value: string): Promise<void> => {
  await store.set(keyName, value);
  await store.save();
  console.log(`[Store] Saved ${keyName}`);
};

/**
 * Load API key from secure store
 * @param keyName - Key identifier
 * @returns API key value or null if not found
 */
export const getApiKey = async (keyName: string): Promise<string | null> => {
  const value = await store.get<string>(keyName);
  return value ?? null;
};

/**
 * Remove API key from store
 * @param keyName - Key identifier
 */
export const removeApiKey = async (keyName: string): Promise<void> => {
  await store.delete(keyName);
  await store.save();
  console.log(`[Store] Deleted ${keyName}`);
};

/**
 * List all stored keys (names only, not values)
 * @returns Array of key names
 */
export const listApiKeys = async (): Promise<string[]> => {
  const keys = await store.keys();
  return keys;
};

/**
 * Check if a specific key exists
 * @param keyName - Key identifier
 * @returns true if key exists
 */
export const hasApiKey = async (keyName: string): Promise<boolean> => {
  return await store.has(keyName);
};

/**
 * Save Cloudflare Zero Trust Token
 * @param token - The Cloudflare tunnel token
 */
export const saveCloudflareToken = async (token: string): Promise<void> => {
  await saveApiKey('cloudflare_token', token);
};

/**
 * Get Cloudflare Zero Trust Token
 * @returns Token or null if not configured
 */
export const getCloudflareToken = async (): Promise<string | null> => {
  return await getApiKey('cloudflare_token');
};

export default store;