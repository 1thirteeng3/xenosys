/**
 * XenoSys Gateway - Security Module
 * HMAC, timing-safe API keys, JWT authentication
 */
import { createHmac, timingSafeEqual, randomBytes, createCipheriv, createDecipheriv } from 'crypto';

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

export class HMACValidator {
  private secret: string;
  private algorithm = 'sha256';

  constructor(secret: string) {
    if (!secret) throw new Error('HMAC secret is required');
    this.secret = secret;
  }

  generateSignature(payload: string): string {
    const hmac = createHmac(this.algorithm, this.secret);
    hmac.update(payload, 'utf8');
    return hmac.digest('hex');
  }

  verifySignature(payload: string, signature: string): boolean {
    const expected = this.generateSignature(payload);
    const expectedBuf = Buffer.from(expected, 'hex');
    const signatureBuf = Buffer.from(signature, 'hex');
    if (expectedBuf.length !== signatureBuf.length) return false;
    return timingSafeEqual(expectedBuf, signatureBuf);
  }

  validateWebhook(payload: string, signature: string | undefined): boolean {
    if (!signature) return false;
    const parts = signature.split('=');
    if (parts.length !== 2) return false;
    const algorithm = parts[0] ?? '';
    const sig = parts[1] ?? '';
    if (algorithm !== 'sha256' || !sig) {
      console.warn('Unsupported HMAC algorithm: ' + algorithm);
      return false;
    }
    return this.verifySignature(payload, sig);
  }
}

export class APIKeyValidator {
  private keys: Map<string, ApiKeyConfig>;

  constructor(keys: Map<string, ApiKeyConfig> = new Map()) {
    this.keys = keys;
  }

  addKey(id: string, config: Omit<ApiKeyConfig, 'key'>): string {
    const key = randomBytes(32).toString('hex');
    this.keys.set(id, { key, ...config });
    return key;
  }

  removeKey(id: string): boolean {
    return this.keys.delete(id);
  }

  validateKey(id: string, providedKey: string): ApiKeyConfig | null {
    const stored = this.keys.get(id);
    if (!stored) return null;

    if (stored.expiresAt && Date.now() > stored.expiresAt) {
      this.keys.delete(id);
      return null;
    }

    const storedBuf = Buffer.from(stored.key, 'hex');
    const providedBuf = Buffer.from(providedKey, 'hex');

    if (storedBuf.length !== providedBuf.length) return null;
    if (!timingSafeEqual(storedBuf, providedBuf)) return null;

    return stored;
  }

  getKey(id: string): ApiKeyConfig | undefined {
    return this.keys.get(id);
  }

  listKeys(): string[] {
    return Array.from(this.keys.keys());
  }
}

export class JWTValidator {
  private secret: string;
  private expiration: string;
  private algorithm = 'HS256';

  constructor(secret: string, expiry = '24h') {
    if (!secret) throw new Error('JWT secret is required');
    this.secret = secret;
    this.expiration = expiry;
  }

  generate(payload: Omit<JWTPayload, 'iat' | 'exp'>): string {
    const header = Buffer.from(JSON.stringify({ alg: this.algorithm, typ: 'JWT' })).toString('base64url');
    const now = Math.floor(Date.now() / 1000);
    const exp = this.parseExpiry(now);

    const payloadObj = { ...payload, iat: now, exp };
    const payloadB64 = Buffer.from(JSON.stringify(payloadObj)).toString('base64url');
    const signature = this.sign(header + '.' + payloadB64);

    return header + '.' + payloadB64 + '.' + signature;
  }

  verify(token: string): JWTPayload | null {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return null;

      const header = parts[0] ?? '';
      const payload = parts[1] ?? '';
      const signature = parts[2] ?? '';

      const expectedSig = this.sign(header + '.' + payload);
      const sigBuf = Buffer.from(signature, 'base64url');
      const expectedBuf = Buffer.from(expectedSig, 'base64url');

      if (!timingSafeEqual(sigBuf, expectedBuf)) return null;

      const payloadObj = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));

      if (payloadObj.exp && Math.floor(Date.now() / 1000) > payloadObj.exp) return null;

      return payloadObj;
    } catch {
      return null;
    }
  }

  extractFromHeader(authHeader: string | undefined): string | null {
    if (!authHeader) return null;
    const parts = authHeader.split(' ');
    if (parts.length !== 2 || parts[0] !== 'Bearer') return null;
    return parts[1] ?? null;
  }

  refresh(token: string): string | null {
    const payload = this.verify(token);
    if (!payload) return null;

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
    const match = this.expiration.match(/^(\d+)([smhd])$/);
    if (!match) return iat + 86400;

    const value = parseInt(match[1] ?? '1', 10);
    const unit = match[2] ?? 'd';

    const multipliers: Record<string, number> = { s: 1, m: 60, h: 3600, d: 86400 };
    return iat + (value * (multipliers[unit] ?? 3600));
  }
}

export class DataEncryptor {
  private key: Buffer;

  constructor(key: string) {
    if (!key) throw new Error('Encryption key is required');
    const hash = createHmac('sha256', key).digest();
    this.key = hash;
  }

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

  decrypt(encrypted: EncryptedData): string {
    if (!encrypted.iv || !encrypted.tag || !encrypted.data) {
      throw new Error('Invalid encrypted payload format');
    }
    const iv = Buffer.from(encrypted.iv, 'hex');
    const tag = Buffer.from(encrypted.tag, 'hex');

    const decipher = createDecipheriv('aes-256-gcm', this.key, iv);
    decipher.setAuthTag(tag);

    let decrypted = decipher.update(encrypted.data, 'hex', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  }
}

export class SecurityManager {
  hmac: HMACValidator | null = null;
  apiKeys: APIKeyValidator | null = null;
  jwt: JWTValidator | null = null;
  encryptor: DataEncryptor | null = null;

  constructor(config: SecurityConfig) {
    if (config.hmacSecret) this.hmac = new HMACValidator(config.hmacSecret);
    if (config.apiKeys) this.apiKeys = new APIKeyValidator(config.apiKeys);
    if (config.jwtSecret) this.jwt = new JWTValidator(config.jwtSecret, config.jwtExpiry);
    if (config.encryptionKey) this.encryptor = new DataEncryptor(config.encryptionKey);
  }

  static fromEnv(): SecurityManager {
    return new SecurityManager({
      hmacSecret: process.env.HMAC_SECRET,
      jwtSecret: process.env.JWT_SECRET,
      jwtExpiry: process.env.JWT_EXPIRY ?? '24h',
      encryptionKey: process.env.ENCRYPTION_KEY,
    });
  }
}

export default SecurityManager;
