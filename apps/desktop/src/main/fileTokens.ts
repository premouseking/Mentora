import { randomUUID } from "node:crypto";
import type { WebContents } from "electron";

interface FileGrant {
  absolutePath: string;
  name: string;
  size: number;
  mime: string;
  owner: WebContents;
  expiresAt: number;
}

const TOKEN_TTL_MS = 30 * 60 * 1000;

/**
 * Issues short-lived, window-bound tokens for user-selected files. The renderer
 * never sees absolute paths and can never ask main to read an arbitrary path
 * (desktop-client-architecture §6.1).
 */
export class FileTokenStore {
  private readonly grants = new Map<string, FileGrant>();

  issue(
    owner: WebContents,
    file: { absolutePath: string; name: string; size: number; mime: string },
  ): string {
    const token = randomUUID();
    this.grants.set(token, {
      ...file,
      owner,
      expiresAt: Date.now() + TOKEN_TTL_MS,
    });
    return token;
  }

  resolve(token: string, requester: WebContents): FileGrant | null {
    const grant = this.grants.get(token);
    if (!grant) return null;
    if (grant.owner !== requester) return null;
    if (grant.expiresAt < Date.now()) {
      this.grants.delete(token);
      return null;
    }
    return grant;
  }

  revokeAllFor(owner: WebContents): void {
    for (const [token, grant] of this.grants) {
      if (grant.owner === owner) this.grants.delete(token);
    }
  }
}
