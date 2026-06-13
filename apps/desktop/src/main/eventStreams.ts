import { randomUUID } from "node:crypto";
import type { WebContents } from "electron";

import type { StreamMessage } from "../shared/desktopApi";
import type { EventStreamOptionsInput } from "../shared/schemas";
import { API_BASE_URL } from "./config";
import { createLogger } from "./logger";
import type { AuthManager } from "./auth";
import { Channels } from "../shared/channels";

const log = createLogger("events");

interface ActiveStream {
  controller: AbortController;
  owner: WebContents;
}

/** 约束：IPC 仅传字节；断线续传由 Last-Event-ID 与 REST 快照兜底（§5.2） */
export class EventStreamBridge {
  private readonly streams = new Map<string, ActiveStream>();

  constructor(private readonly auth: AuthManager) {}

  async open(
    sender: WebContents,
    options: EventStreamOptionsInput,
  ): Promise<{ streamId: string }> {
    const streamId = randomUUID();
    const controller = new AbortController();
    this.streams.set(streamId, { controller, owner: sender });

    void this.pump(streamId, sender, options, controller);
    return { streamId };
  }

  abort(streamId: string): void {
    const stream = this.streams.get(streamId);
    if (!stream) return;
    stream.controller.abort();
    this.streams.delete(streamId);
  }

  abortAllFor(sender: WebContents): void {
    for (const [streamId, stream] of this.streams) {
      if (stream.owner === sender) {
        stream.controller.abort();
        this.streams.delete(streamId);
      }
    }
  }

  private emit(sender: WebContents, message: StreamMessage): void {
    if (sender.isDestroyed()) return;
    sender.send(Channels.events.message, message);
  }

  private async pump(
    streamId: string,
    sender: WebContents,
    options: EventStreamOptionsInput,
    controller: AbortController,
  ): Promise<void> {
    try {
      const headers: Record<string, string> = { accept: "text/event-stream" };
      if (options.lastEventId) headers["last-event-id"] = options.lastEventId;
      const token = await this.auth.getAccessToken();
      if (token) headers.authorization = `Bearer ${token}`;

      const response = await fetch(API_BASE_URL + options.path, {
        headers,
        signal: controller.signal,
      });

      this.emit(sender, { streamId, kind: "head", status: response.status });
      if (!response.ok || !response.body) {
        this.emit(sender, {
          streamId,
          kind: "error",
          message: `stream open failed: ${response.status}`,
        });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let boundary: number;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          this.dispatchEvent(streamId, sender, rawEvent);
        }
      }
      this.emit(sender, { streamId, kind: "end" });
    } catch (err) {
      if (controller.signal.aborted) return;
      log.warn("Event stream errored", { streamId, message: String(err) });
      this.emit(sender, { streamId, kind: "error", message: String(err) });
    } finally {
      this.streams.delete(streamId);
    }
  }

  private dispatchEvent(
    streamId: string,
    sender: WebContents,
    rawEvent: string,
  ): void {
    let id: string | undefined;
    let event: string | undefined;
    const dataLines: string[] = [];

    for (const line of rawEvent.split("\n")) {
      if (line.startsWith(":")) continue;
      const sep = line.indexOf(":");
      const field = sep === -1 ? line : line.slice(0, sep);
      const value = sep === -1 ? "" : line.slice(sep + 1).replace(/^ /, "");
      if (field === "id") id = value;
      else if (field === "event") event = value;
      else if (field === "data") dataLines.push(value);
    }

    if (dataLines.length === 0 && !event) return;
    this.emit(sender, {
      streamId,
      kind: "event",
      id,
      event,
      data: dataLines.join("\n"),
    });
  }
}
