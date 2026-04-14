#!/usr/bin/env node
/**
 * XenoSys Gateway Build Script
 * -----------------------------
 * Creates bundled Node.js executable for Gateway sidecar
 * 
 * Usage:
 *   node build_gateway.js
 * 
 * Output:
 *   dist/xenosys-gateway-bin (or .exe on Windows)
 * 
 * Requires: pkg (npm install -g pkg)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const OUT_DIR = 'sidecars';
const BUNDLE_NAME = 'xenosys-gateway-bin';

// Ensure output directory exists
if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

console.log('🔨 Building Gateway sidecar...');

// Build TypeScript first
console.log('📦 Compiling TypeScript...');
execSync('npm run build', { cwd: 'nexus/gateway', stdio: 'inherit' });

// Bundle with pkg
console.log('📦 Creating standalone executable...');
const platform = process.platform;
const ext = platform === 'win32' ? '.exe' : '';

const pkgCmd = `pkg nexus/gateway/dist/gateway/server.js --output ${OUT_DIR}/${BUNDLE_NAME}${ext} --public`;
execSync(pkgCmd, { stdio: 'inherit' });

console.log(`✅ Gateway built: ${OUT_DIR}/${BUNDLE_NAME}${ext}`);