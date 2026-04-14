/**
 * XenoSys Gateway - Security Module
 * HMAC, timing-safe API keys, JWT authentication
 */

import { createHmac, timingSafeEqual, randomBytes, createCipheriv, createDecipheriv } from 'crypto';
import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';

// ============================================================================
// Types
// ============================================================================

export interface SecurityConfig {
  hmacSecret?: string;
  apiKeys?: Map<string, ApiKeyConfig>;
  jwtSecret?: string;
  jwtExpiry?: string;
  encryptionKey?: string;
}

export interface ApiKeyConfig {
  key: string;
  name: string;
  permissions: string[];
  createdAt: number;
  expiresAt?: number;
}

export interface JWTPayload {
  userId: string;
  email?: string;
  roles: string[];
  iat: number;
  exp: number;
}

export interface EncryptedData {
  iv: string;
  data: string;
  tag: string;
}

// ============================================================================
// HMAC Signature Validation
// ============================================================================

export class HMACValidator {
  private secret: string;
  private algorithm = 'sha256';

  constructor(secret: string) {
    if (!secret) {
      throw new Error('HMAC secret is required');
    }
    this.secret = secret;
  }

  /**
   * Generate HMAC signature for a payload
   */
  generateSignature(payload: string): string {
    const hmac = createHmac(this.algorithm, this.secret);
    hmac.update(payload, 'utf8');
    return hmac.digest('hex');
  }

  /**
   * Verify HMAC signature - constant time comparison
   */
  verifySignature(payload: string, signature: string): boolean {
    const expected = this.generateSignature(payload);
    
    // Convert to buffers for timing-safe comparison
    const expectedBuf = Buffer.from(expected, 'hex');
    const signatureBuf = Buffer.from(signature, 'hex');
    
    // Must match length exactly
    if (expectedBuf.length !== signatureBuf.length) {
      return false;
    }
    
    // Timing-safe comparison
    return timingSafeEqual(expectedBuf, signatureBuf);
  }

  /**
   * Validate webhook payload with signature
   */
  validateWebhook(payload: string, signature: string): boolean {
    if (!signature) {
      return false;
    }
    
    // Support multiple signature algorithms
    const parts = signature.split('=');
    if (parts.length !== 2) {
      return false;
    }
    
    const algorithm = parts[0];
    const sig = parts[1];
    
    // Only support sha256 for now
    if (algorithm !== 'sha256') {
      console.warn(`Unsupported HMAC algorithm: ${algorithm}`);
      return false;
    }
    
    return this.verifySignature(payload, sig);
  }
}

// ============================================================================
// Timing-Safe API Key Comparison
// ============================================================================

export class APIKeyValidator {
  private keys: Map<string, ApiKeyConfig>;

  constructor(keys: Map<string, ApiKeyConfig> = new Map()) {
    this.keys = keys;
  }

  /**
   * Add an API key to the store
   */
  addKey(id: string, config: Omit<ApiKeyConfig, 'key'>): string {
    const key = randomBytes(32).toString('hex');
    this.keys.set(id, {
      key,
      ...config,
    });
    return key;
  }

  /**
   * Remove an API key
   */
  removeKey(id: string): boolean {
    return this.keys.delete(id);
  }

  /**
   * Validate API key with timing-safe comparison
   */
  validateKey(id: string, providedKey: string): ApiKeyConfig | null {
    const stored = this.keys.get(id);
    
    if (!stored) {
      return null;
    }
    
    // Check expiration
    if (stored.expiresAt && Date.now() > stored.expiresAt) {
      this.keys.delete(id);
      return null;
    }
    
    // Timing-safe comparison
    const storedBuf = Buffer.from(stored.key, 'hex');
    const providedBuf = Buffer.from(providedKey, 'hex');
    
    // Must match length exactly
    if (storedBuf.length !== providedBuf.length) {
      return null;
    }
    
    if (!timingSafeEqual(storedBuf, providedBuf)) {
      return null;
    }
    
    return stored;
  }

  /**
   * Get key config without validation
   */
  getKey(id: string): ApiKeyConfig | undefined {
    return this.keys.get(id);
  }

  /**
   * List all key IDs (not the keys themselves)
   */
  listKeys(): string[] {
    return Array.from(this.keys.keys());
  }
}

// ============================================================================
// JWT Authentication
// ============================================================================

export class JWTValidator {
  private secret: string;
  private expiry: string;
  private algorithm = 'HS256';

  constructor(secret: string, expiry = '24h') {
    if (!secret) {
      throw new Error('JWT secret is required');
    }
    this.secret = secret;
    this.expiry = expiry;
  }

  /**
   * Generate JWT token
   */
  generate(payload: Omit<JWTPayload, 'iat' | 'exp'>): string {
    const header = Buffer.from(JSON.stringify({ alg: this.algorithm, typ: 'JWT' })).toString('base64url');
    
    const now = Math.floor(Date.now() / 1000);
    const exp = this.parseExpiry(now);
    
    const payloadObj = {
      ...payload,
      iat: now,
      exp,
    };
    
    const payloadB64 = Buffer.from(JSON.stringify(payloadObj)).toString('base64url');
    
    const signature = this.sign(`${header}.${payloadB64}`);
    
    return `${header}.${payloadB64}.${signature}`;
  }

  /**
   * Verify and decode JWT token
   */
  verify(token: string): JWTPayload | null {
    try {
      const parts = token.split('.');
      
      if (parts.length !== 3) {
        return null;
      }
      
      const [header, payload, signature] = parts;
      
      // Verify signature
      const expectedSig = this.sign(`${header}.${payload}`);
      const sigBuf = Buffer.from(signature, 'base64url');
      const expectedBuf = Buffer.from(expectedSig, 'base64url');
      
      if (!timingSafeEqual(sigBuf, expectedBuf)) {
        return null;
      }
      
      // Decode payload
      const payloadObj = JSON.parse(Buffer.from(payload, 'base64url').toString());
      
      // Check expiration
      if (payloadObj.exp && Math.floor(Date.now() / 1000) > payloadObj.exp) {
        return null;
      }
      
      return payloadObj;
    } catch {
      return null;
    }
  }

  /**
   * Extract token from Authorization header
   */
  extractFromHeader(authHeader: string): string | null {
    if (!authHeader) {
      return null;
    }
    
    const parts = authHeader.split(' ');
    
    if (parts.length !== 2 || parts[0] !== 'Bearer') {
      return null;
    }
    
    return parts[1];
  }

  /**
   * Refresh a token (generate new with same payload)
   */
  refresh(token: string): string | null {
    const payload = this.verify(token);
    
    if (!payload) {
      return null;
    }
    
    // Generate new token with same user data but new expiry
    return this.generate({
      userId: payload.userId,
      email: payload.email,
      roles: payload.roles,
    });
  }

  private sign(data: string): string {
    const hmac = createHmac('sha256', this.secret);
    hmac.update(data, 'utf8');
    return hmac.digest('base64url');
  }

  private parseExpiry(iat: number): number {
    const match = this.expiry.match(/^(\d+)([smhd])$/);
    
    if (!match) {
      return iat + 86400; // Default 24 hours
    }
    
    const value = parseInt(match[1], 10);
    const unit = match[2];
    
    const multipliers: Record<string, number> = {
      s: 1,
      m: 60,
      h: 3600,
      d: 86400,
    };
    
    return iat + (value * (multipliers[unit] || 3600));
  }
}

// ============================================================================
// Encryption (for sensitive data at rest)
// ============================================================================

export class DataEncryptor {
  private key: Buffer;

  constructor(key: string) {
    if (!key) {
      throw new Error('Encryption key is required');
    }
    
    // Derive 32-byte key from provided key
    const hash = createHmac('sha256', key).digest();
    this.key = hash;
  }

  /**
   * Encrypt data using AES-256-GCM
   */
  encrypt(plaintext: string): EncryptedData {
    const iv = randomBytes(16);
    const cipher = createCipheriv('aes-256-gcm', this.key, iv);
    
    let encrypted = cipher.update(plaintext, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    
    const tag = cipher.getAuthTag();
    
    return {
      iv: iv.toString('hex'),
      data: encrypted,
      tag: tag.toString('hex'),
    };
  }

  /**
   * Decrypt data using AES-256-GCM
   */
  decrypt(encrypted: EncryptedData): string {
    const iv = Buffer.from(encrypted.iv, 'hex');
    const tag = Buffer.from(encrypted.tag, 'hex');
    
    const decipher = createDecipheriv('aes-256-gcm', this.key, iv);
    decipher.setAuthTag(tag);
    
    let decrypted = decipher.update(encrypted.data, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    
    return decrypted;
  }
}

// ============================================================================
// Security Factory
// ============================================================================

export class SecurityManager {
  hmac: HMACValidator | null = null;
  apiKeys: APIKeyValidator | null = null;
  jwt: JWTValidator | null = null;
  encryptor: DataEncryptor | null = null;

  constructor(config: SecurityConfig) {
    if (config.hmacSecret) {
      this.hmac = new HMACValidator(config.hmacSecret);
    }
    
    if (config.apiKeys) {
      this.apiKeys = new APIKeyValidator(config.apiKeys);
    }
    
    if (config.jwtSecret) {
      this.jwt = new JWTValidator(config.jwtSecret, config.jwtExpiry);
    }
    
    if (config.encryptionKey) {
      this.encryptor = new DataEncryptor(config.encryptionKey);
    }
  }

  /**
   * Create from environment variables
   */
  static fromEnv(): SecurityManager {
    return new SecurityManager({
      hmacSecret: process.env.HMAC_SECRET,
      jwtSecret: process.env.JWT_SECRET,
      jwtExpiry: process.env.JWT_EXPIRY || '24h',
      encryptionKey: process.env.ENCRYPTION_KEY,
    });
  }
}

export default SecurityManager;