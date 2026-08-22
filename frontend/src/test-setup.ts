// Global test setup for jsdom environment
// Provides polyfills for browser APIs not available in jsdom

if (typeof globalThis.ResizeObserver === 'undefined') {
  (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
}

// Mock getBoundingClientRect to return reasonable sizes for subject cards
// so that MallaConnections can calculate positions in test
if (typeof Element !== 'undefined') {
  const ORIGINAL_GET_BOUNDING_CLIENT_RECT = Element.prototype.getBoundingClientRect;

  Element.prototype.getBoundingClientRect = function () {
    const code = (this as HTMLElement).dataset?.subjectCode;
    if (code) {
      return {
        top: 100,
        left: 200,
        width: 200,
        height: 100,
        bottom: 200,
        right: 400,
        x: 200,
        y: 100,
        toJSON(): string { return ''; },
      } as DOMRect;
    }
    // semester-grid container needs non-zero dimensions for the SVG overlay
    if ((this as HTMLElement).classList?.contains('semester-grid')) {
      return {
        top: 0,
        left: 0,
        width: 2200,
        height: 800,
        bottom: 800,
        right: 2200,
        x: 0,
        y: 0,
        toJSON(): string { return ''; },
      } as DOMRect;
    }
    return ORIGINAL_GET_BOUNDING_CLIENT_RECT.call(this);
  };
}
