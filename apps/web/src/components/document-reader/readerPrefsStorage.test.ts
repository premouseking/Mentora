import { beforeEach, describe, expect, it, vi } from "vitest";

import { readReaderPrefs, writeReaderPrefs } from "./readerPrefsStorage";

function createSessionStorageMock(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => [...store.keys()][index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
  };
}

describe("readerPrefsStorage", () => {
  beforeEach(() => {
    vi.stubGlobal("sessionStorage", createSessionStorageMock());
  });

  it("persists page scale and sidebar state per resource", () => {
    writeReaderPrefs("res-1", { page: 8, scale: 1.25, sidebarCollapsed: true });
    expect(readReaderPrefs("res-1")).toEqual({
      page: 8,
      scale: 1.25,
      sidebarCollapsed: true,
    });
  });

  it("merges patches without overwriting unrelated resources", () => {
    writeReaderPrefs("res-1", { page: 2 });
    writeReaderPrefs("res-2", { page: 5 });
    writeReaderPrefs("res-1", { scale: 1.5 });
    expect(readReaderPrefs("res-1")).toEqual({ page: 2, scale: 1.5 });
    expect(readReaderPrefs("res-2")).toEqual({ page: 5 });
  });
});
