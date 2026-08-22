import { useEffect, useRef, useState } from 'react';

import { getDocument } from '../lib/pdf/pdf-worker';

export interface PdfViewerProps {
  src: string;
  title?: string;
}

export function PdfViewer({ src, title = 'Calendario Académico' }: PdfViewerProps) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    let destroy: (() => Promise<void>) | null = null;
    const renderPdf = async (): Promise<void> => {
      setStatus('loading');
      try {
        const task = await getDocument({ url: src });
        destroy = async () => { await task.destroy(); };
        const pdf = await task.promise;
        if (cancelled || !container.current) return;
        container.current.replaceChildren();
        for (let number = 1; number <= pdf.numPages; number += 1) {
          const page = await pdf.getPage(number);
          if (cancelled || !container.current) return;
          const base = page.getViewport({ scale: 1 });
          const width = Math.min(Math.max(container.current.clientWidth - 24, 320), 1100);
          const viewport = page.getViewport({ scale: Math.max(0.65, width / base.width) });
          const canvas = document.createElement('canvas');
          canvas.className = 'pdf-page';
          canvas.width = Math.ceil(viewport.width);
          canvas.height = Math.ceil(viewport.height);
          canvas.setAttribute('aria-label', `${title}, página ${number}`);
          container.current.append(canvas);
          const context = canvas.getContext('2d');
          if (!context) throw new Error('Canvas no disponible');
          await page.render({ canvasContext: context, canvas, viewport }).promise;
        }
        if (!cancelled) setStatus('ready');
      } catch {
        if (!cancelled) setStatus('error');
      }
    };
    void renderPdf();
    return () => {
      cancelled = true;
      void destroy?.();
    };
  }, [src, title]);

  return (
    <section className="pdf-viewer surface" aria-busy={status === 'loading'}>
      {status === 'loading' && <p className="empty-state">Cargando calendario…</p>}
      {status === 'error' && (
        <div className="pdf-fallback" role="status">
          <h2>No se pudo mostrar el visor integrado</h2>
          <p>El calendario oficial todavía no está disponible o tu navegador no puede abrirlo.</p>
          <a className="button button--secondary" href={src} target="_blank" rel="noopener noreferrer">Ver el PDF en el navegador</a>
        </div>
      )}
      <div ref={container} className="pdf-pages" hidden={status === 'error'} />
      {status === 'ready' && <a className="pdf-external" href={src} target="_blank" rel="noopener noreferrer">Si tu celular no muestra el visor, ver el PDF en el navegador</a>}
    </section>
  );
}
