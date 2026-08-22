import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

export interface RenderedComponent {
  container: HTMLDivElement;
  cleanup: () => Promise<void>;
}

export async function renderComponent(node: ReactNode): Promise<RenderedComponent> {
  const container = document.createElement('div');
  document.body.append(container);
  const root: Root = createRoot(container);
  await act(async () => {
    root.render(node);
  });
  return {
    container,
    cleanup: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}

export function elementByText(container: ParentNode, text: string): HTMLElement {
  const element = [...container.querySelectorAll<HTMLElement>('*')]
    .find((candidate) => candidate.textContent?.trim() === text);
  if (!element) throw new Error(`No se encontro el texto: ${text}`);
  return element;
}

export function buttonByName(container: ParentNode, name: string): HTMLButtonElement {
  const button = [...container.querySelectorAll<HTMLButtonElement>('button')]
    .find((candidate) => candidate.textContent?.trim() === name || candidate.getAttribute('aria-label') === name);
  if (!button) throw new Error(`No se encontro el boton: ${name}`);
  return button;
}

export async function click(element: HTMLElement): Promise<void> {
  await act(async () => element.click());
}

export async function enterValue(element: HTMLInputElement, value: string): Promise<void> {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(element, value);
  await act(async () => element.dispatchEvent(new Event('input', { bubbles: true })));
}

export async function tick(): Promise<void> {
  await act(async () => Promise.resolve());
}
