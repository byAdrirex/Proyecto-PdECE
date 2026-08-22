type PdfJs = typeof import('pdfjs-dist');
type DocumentSource = Parameters<PdfJs['getDocument']>[0];
type LoadingTask = ReturnType<PdfJs['getDocument']>;

export async function getDocument(source: DocumentSource): Promise<LoadingTask> {
  const [pdfjs, workerAsset] = await Promise.all([
    import('pdfjs-dist'),
    import('pdfjs-dist/build/pdf.worker.min.mjs?url'),
  ]);

  pdfjs.GlobalWorkerOptions.workerSrc = workerAsset.default;
  return pdfjs.getDocument(source);
}
