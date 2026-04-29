import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "../i18n";

function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    key(index: number) {
      return Array.from(store.keys())[index] || null;
    },
    getItem(key: string) {
      return store.get(key) || null;
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store.clear();
    }
  } as Storage;
}

let hasUsableLocalStorage = false;
try {
  hasUsableLocalStorage = typeof window.localStorage?.clear === "function";
} catch {
  hasUsableLocalStorage = false;
}

if (!hasUsableLocalStorage) {
  const storage = createMemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: storage });
} else {
  let hasUsableGlobalLocalStorage = false;
  try {
    hasUsableGlobalLocalStorage = typeof globalThis.localStorage?.clear === "function";
  } catch {
    hasUsableGlobalLocalStorage = false;
  }
  if (!hasUsableGlobalLocalStorage) {
    Object.defineProperty(globalThis, "localStorage", { configurable: true, value: window.localStorage });
  }
}

afterEach(() => {
  cleanup();
});
