import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import * as pdfjsLib from 'pdfjs-dist';
import { PrintConfig, PaperSize, UploadedFile, PrintColorMode } from '../../types';
import { usePricing } from '../../hooks/usePricing';
import { Loader2 } from 'lucide-react';

pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;
import { 
  FileText, 
  HardDrive, 
  Pencil, 
  ArrowUpDown, 
  Palette, 
  CircleDot, 
  ChevronDown, 
  Info, 
  ArrowRight, 
  ShieldCheck,
  QrCode,
  Eye,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Trash2,
  Settings,
  Check,
  X,
  AlertCircle
} from 'lucide-react';

interface StepConfigureProps {
  config: PrintConfig;
  onChangeConfig: (newConfig: PrintConfig) => void;
  onBack: () => void;
  onNext: () => void;
  onRemoveFile?: () => void;
}

interface PdfCanvasPageProps {
  url: string;
  pageNum: number;
  colorMode: PrintColorMode;
  onRenderError?: () => void;
}

const PdfCanvasPage: React.FC<PdfCanvasPageProps> = ({ url, pageNum, colorMode, onRenderError }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let isCancelled = false;

    const renderPdf = async () => {
      try {
        const pdf = await pdfjsLib.getDocument(url).promise;
        if (isCancelled) return;
        const validPage = Math.min(Math.max(1, pageNum), pdf.numPages);
        const page = await pdf.getPage(validPage);
        if (isCancelled || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const context = canvas.getContext('2d');
        if (!context) return;

        const viewport = page.getViewport({ scale: 1.2 });
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        await page.render({
          canvasContext: context,
          viewport,
        } as any).promise;
      } catch (err) {
        console.warn('PDF canvas render fallback:', err);
        if (!isCancelled && onRenderError) {
          onRenderError();
        }
      }
    };

    renderPdf();

    return () => {
      isCancelled = true;
    };
  }, [url, pageNum, onRenderError]);

  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden bg-white rounded-lg p-1">
      <span className="absolute top-1 left-1 z-10 text-[8px] font-bold text-slate-700 bg-white/90 border border-slate-200 px-1 py-0.2 rounded-xs shadow-2xs">
        Page {pageNum}
      </span>
      <canvas
        ref={canvasRef}
        className={`max-h-full max-w-full object-contain transition-all ${
          colorMode === 'bw' ? 'grayscale contrast-125' : ''
        }`}
      />
    </div>
  );
};

/* Page Preview Cell Component for PDF, DOC, DOCX, Images, etc. without Chrome iframe blocking */
interface PagePreviewCellProps {
  file: UploadedFile | null;
  pageNum: number;
  totalPageCount: number;
  colorMode: PrintColorMode;
  isCompact?: boolean;
}

const PagePreviewCell: React.FC<PagePreviewCellProps> = ({
  file,
  pageNum,
  totalPageCount,
  colorMode,
  isCompact = false,
}) => {
  const [imgError, setImgError] = useState(false);
  const [pdfError, setPdfError] = useState(false);

  const fileName = file ? file.name : 'Document.pdf';
  const extension = fileName.includes('.') ? fileName.split('.').pop()?.toLowerCase() || '' : 'pdf';
  const isImage = (file?.type?.startsWith('image/') || ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(extension)) && !imgError;
  const isPdf = (file?.type === 'application/pdf' || extension === 'pdf') && !pdfError;
  const cleanTitle = fileName.replace(/\.[^/.]+$/, '').replace(/[_\-]/g, ' ');

  if (isImage && file?.previewUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center overflow-hidden bg-white rounded-lg relative p-1">
        <span className="absolute top-1 left-1 z-10 text-[8px] font-bold text-slate-700 bg-white/90 border border-slate-200 px-1 py-0.2 rounded-xs shadow-2xs">
          Page {pageNum}
        </span>
        <img
          src={file.previewUrl}
          alt={`Page ${pageNum}`}
          className={`max-h-full max-w-full object-contain rounded-xs transition-all ${
            colorMode === 'bw' ? 'grayscale contrast-125' : ''
          }`}
          onError={() => setImgError(true)}
        />
      </div>
    );
  }

  if (isPdf && file?.previewUrl) {
    return (
      <PdfCanvasPage 
        url={file.previewUrl} 
        pageNum={pageNum} 
        colorMode={colorMode} 
        onRenderError={() => setPdfError(true)} 
      />
    );
  }

  // Document page layout (DOC / DOCX / TXT / PPT / Fallback)
  return (
    <div className={`w-full h-full bg-white border border-slate-200/90 rounded-lg p-2 sm:p-2.5 flex flex-col justify-between overflow-hidden text-left select-none relative shadow-2xs ${
      colorMode === 'bw' ? 'grayscale contrast-125' : ''
    }`}>
      {/* Top Banner / Header */}
      <div className="space-y-1">
        <div className="flex items-center justify-between border-b border-slate-100 pb-1 gap-1">
          <span className="text-[9px] font-extrabold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded tracking-wide uppercase truncate max-w-[75%]">
            {cleanTitle}
          </span>
          <span className="text-[8px] font-extrabold text-slate-500 bg-slate-100 px-1 py-0.5 rounded uppercase shrink-0">
            {extension.toUpperCase()}
          </span>
        </div>

        {!isCompact && (
          <h5 className="text-[11px] font-extrabold text-slate-900 leading-tight pt-0.5 truncate">
            {pageNum === 1
              ? 'Executive Summary & Introduction'
              : pageNum === 2
              ? 'Section 2 — Technical Specifications'
              : pageNum === 3
              ? 'Section 3 — Cost Breakdown & Details'
              : `Chapter ${pageNum} — Project Documentation`}
          </h5>
        )}
      </div>

      {/* Simulated Document Content Lines */}
      <div className="space-y-1 py-1 my-auto w-full">
        <div className="h-1.5 bg-slate-300 rounded-full w-full" />
        <div className="h-1.5 bg-slate-200 rounded-full w-[94%]" />
        <div className="h-1.5 bg-slate-200 rounded-full w-[88%]" />
        {!isCompact && (
          <>
            <div className="h-1.5 bg-slate-200 rounded-full w-[96%]" />
            <div className="h-1.5 bg-slate-200 rounded-full w-[65%]" />
            <div className="pt-1 flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full shrink-0" />
              <div className="h-1 bg-slate-300 rounded-full w-4/5" />
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full shrink-0" />
              <div className="h-1 bg-slate-300 rounded-full w-3/5" />
            </div>
          </>
        )}
      </div>

      {/* Footer Page Stamp */}
      <div className="border-t border-slate-100 pt-1 flex items-center justify-between text-[8px] text-slate-400 font-medium">
        <span className="truncate">Doc #{pageNum}</span>
        <span className="font-bold text-slate-600 shrink-0">Page {pageNum} of {totalPageCount}</span>
      </div>
    </div>
  );
};

/* Document Preview Card Component */
const DocumentPreviewCard: React.FC<{
  file: UploadedFile | null;
  colorMode: PrintColorMode;
  pagesPerSheet?: '1 on 1' | '2 on 1' | '4 on 1' | '6 on 1';
  orientation?: 'portrait' | 'landscape';
  onRemoveFile?: () => void;
}> = ({ file, colorMode, pagesPerSheet = '1 on 1', orientation = 'portrait', onRemoveFile }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const pageCount = file ? file.pageCount : 12;
  const fileName = file ? file.name : 'proposal_v2.pdf';

  const isLandscape = orientation === 'landscape';

  const stepSize = pagesPerSheet === '2 on 1' ? 2 : pagesPerSheet === '4 on 1' ? 4 : pagesPerSheet === '6 on 1' ? 6 : 1;

  const handlePrev = () => setCurrentPage((p) => Math.max(1, p - stepSize));
  const handleNext = () => setCurrentPage((p) => Math.min(pageCount, p + stepSize));

  const renderSheetBody = (isModal = false) => {
    if (pagesPerSheet === '2 on 1') {
      const items = [currentPage, currentPage + 1];
      const gridClass = isLandscape
        ? 'grid grid-cols-2 gap-2.5 w-full h-full'
        : 'grid grid-rows-2 gap-2.5 w-full h-full';
      return (
        <div className={gridClass}>
          {items.map((pageNum, idx) => {
            const hasPage = pageNum <= pageCount;
            return (
              <div 
                key={idx} 
                className={`relative border border-dashed border-slate-300/90 rounded-xl p-1 flex items-center justify-center overflow-hidden transition-all ${
                  hasPage ? 'bg-slate-50/40' : 'bg-slate-50/10'
                }`}
              >
                {hasPage ? (
                  <PagePreviewCell 
                    file={file} 
                    pageNum={pageNum} 
                    totalPageCount={pageCount} 
                    colorMode={colorMode} 
                    isCompact={true}
                  />
                ) : null}
              </div>
            );
          })}
        </div>
      );
    }

    if (pagesPerSheet === '4 on 1') {
      const offsets = [0, 1, 2, 3];
      const gridClass = 'grid grid-cols-2 grid-rows-2 gap-2 w-full h-full';
      return (
        <div className={gridClass}>
          {offsets.map((offset) => {
            const pageNum = currentPage + offset;
            const hasPage = pageNum <= pageCount;
            return (
              <div 
                key={offset} 
                className={`relative border border-dashed border-slate-300/90 rounded-xl p-1 flex items-center justify-center overflow-hidden transition-all ${
                  hasPage ? 'bg-slate-50/40' : 'bg-slate-50/10'
                }`}
              >
                {hasPage ? (
                  <PagePreviewCell 
                    file={file} 
                    pageNum={pageNum} 
                    totalPageCount={pageCount} 
                    colorMode={colorMode} 
                    isCompact={true}
                  />
                ) : null}
              </div>
            );
          })}
        </div>
      );
    }

    if (pagesPerSheet === '6 on 1') {
      const offsets = [0, 1, 2, 3, 4, 5];
      const gridClass = isLandscape
        ? 'grid grid-cols-3 grid-rows-2 gap-1.5 w-full h-full'
        : 'grid grid-cols-2 grid-rows-3 gap-1.5 w-full h-full';
      return (
        <div className={gridClass}>
          {offsets.map((offset) => {
            const pageNum = currentPage + offset;
            const hasPage = pageNum <= pageCount;
            return (
              <div 
                key={offset} 
                className={`relative border border-dashed border-slate-300/90 rounded-lg p-0.5 flex items-center justify-center overflow-hidden transition-all ${
                  hasPage ? 'bg-slate-50/40' : 'bg-slate-50/10'
                }`}
              >
                {hasPage ? (
                  <PagePreviewCell 
                    file={file} 
                    pageNum={pageNum} 
                    totalPageCount={pageCount} 
                    colorMode={colorMode} 
                    isCompact={true}
                  />
                ) : null}
              </div>
            );
          })}
        </div>
      );
    }

    // Default: 1 on 1
    return (
      <div className="w-full h-full border border-dashed border-slate-300/90 rounded-xl p-1.5 flex items-center justify-center overflow-hidden bg-slate-50/20">
        <PagePreviewCell 
          file={file} 
          pageNum={currentPage} 
          totalPageCount={pageCount} 
          colorMode={colorMode} 
          isCompact={false}
        />
      </div>
    );
  };

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs space-y-4">
      {/* Header with Title & Preview Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Eye className="w-4 h-4 stroke-[2.2]" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-900">Document Preview</h4>
            <p className="text-[11px] text-slate-500 font-medium">
              {colorMode === 'bw' ? 'Black & White Mode' : 'Color Mode'} • {pagesPerSheet} Layout • {isLandscape ? 'Landscape' : 'Portrait'} • Page {currentPage} of {pageCount}
            </p>
          </div>
        </div>

        {/* Controls: Page Navigator & Zoom */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Page Switcher */}
          <div className="flex items-center gap-1 bg-slate-100/80 p-1 rounded-xl text-xs font-semibold">
            <button
              type="button"
              onClick={handlePrev}
              disabled={currentPage <= 1}
              className="p-1 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer transition-colors"
              title="Previous page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="px-2 text-slate-700 min-w-[50px] text-center">
              {currentPage} / {pageCount}
            </span>
            <button
              type="button"
              onClick={handleNext}
              disabled={currentPage >= pageCount}
              className="p-1 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer transition-colors"
              title="Next page"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-0.5 bg-slate-100/80 p-1 rounded-xl text-xs">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(75, z - 15))}
              className="p-1 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-white cursor-pointer transition-colors"
              title="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="px-1.5 font-medium text-slate-600 text-[11px]">{zoom}%</span>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(150, z + 15))}
              className="p-1 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-white cursor-pointer transition-colors"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200/70 text-slate-600 cursor-pointer transition-colors"
            title="Toggle full preview"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Preview Screen Canvas Container */}
      <div className={`relative bg-slate-100/80 rounded-2xl p-4 sm:p-6 overflow-hidden transition-all flex items-center justify-center min-h-[380px] max-h-[500px] border border-slate-200/60 ${
        colorMode === 'bw' ? 'filter grayscale contrast-[1.05]' : ''
      }`}>
        {/* Paper Sheet Preview Container matching reference image */}
        <div 
          style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top center' }}
          className={`bg-white rounded-2xl shadow-md border border-slate-200/90 p-4 sm:p-5 flex flex-col justify-between transition-all duration-300 select-none relative ${
            isLandscape 
              ? 'w-full max-w-[420px] sm:max-w-[460px] aspect-[1.38/1]' 
              : 'w-full max-w-[300px] sm:max-w-[330px] aspect-[1/1.38]'
          }`}
        >
          {/* Top-Right Trash Delete Button */}
          <button
            type="button"
            onClick={onRemoveFile}
            className="absolute top-3 right-3 z-20 w-8 h-8 rounded-xl bg-red-50/80 hover:bg-red-100 border border-red-200/80 text-red-500 flex items-center justify-center shadow-2xs transition-all cursor-pointer active:scale-95"
            title="Delete / Remove file"
          >
            <Trash2 className="w-4 h-4 stroke-[2]" />
          </button>

          {/* Render Preview Grid / Slots */}
          <div className="w-full flex-1 flex items-center justify-center overflow-hidden py-1">
            {renderSheetBody(false)}
          </div>

          {/* Bottom Floating PREVIEW Button */}
          <div className="mt-3 flex justify-center w-full z-10">
            <button
              type="button"
              onClick={() => setIsFullscreen(true)}
              className="w-full bg-white border border-slate-200/90 shadow-xs hover:shadow-md py-2 px-4 rounded-xl text-slate-700 font-extrabold text-xs flex items-center justify-center gap-2 uppercase tracking-wider cursor-pointer transition-all active:scale-95"
            >
              <Maximize2 className="w-4 h-4 text-slate-600 stroke-[2.2]" />
              <span>PREVIEW</span>
            </button>
          </div>
        </div>
      </div>

      {/* Page Thumbnails Bar */}
      <div className="pt-1">
        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
          {Array.from({ length: Math.min(pageCount, 12) }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setCurrentPage(p)}
              className={`shrink-0 w-12 h-16 rounded-lg border-2 p-0.5 flex flex-col items-center justify-between transition-all cursor-pointer overflow-hidden ${
                currentPage === p
                  ? 'border-blue-600 bg-blue-50/20 shadow-xs scale-105'
                  : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
              }`}
            >
              <div className="w-full flex-1 rounded overflow-hidden flex items-center justify-center">
                <PagePreviewCell
                  file={file}
                  pageNum={p}
                  totalPageCount={pageCount}
                  colorMode={colorMode}
                  isCompact={true}
                />
              </div>
              <span className={`text-[9px] font-semibold mt-0.5 ${currentPage === p ? 'text-blue-600' : 'text-slate-500'}`}>
                {p}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Fullscreen Overlay Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 max-w-2xl w-full max-h-[90vh] flex flex-col space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Eye className="w-5 h-5 text-blue-600" />
                <h3 className="font-bold text-slate-900">{fileName} — Full Preview ({pagesPerSheet})</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsFullscreen(false)}
                className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 cursor-pointer font-bold text-xs"
              >
                Close Preview
              </button>
            </div>

            <div className="flex-1 overflow-y-auto flex items-center justify-center p-4 bg-slate-100 rounded-2xl">
              <div className={`bg-white w-full rounded-xl shadow-xl border border-slate-200 p-6 flex flex-col justify-between transition-all duration-300 ${
                isLandscape ? 'max-w-[540px] aspect-[1.38/1]' : 'max-w-[400px] aspect-[1/1.38]'
              } ${
                colorMode === 'bw' ? 'filter grayscale contrast-[1.05]' : ''
              }`}>
                <div className="border-b border-slate-200 pb-3 flex justify-between items-center text-xs text-slate-500 font-semibold">
                  <span>{fileName}</span>
                  <span>Page {currentPage} of {pageCount} • {pagesPerSheet}</span>
                </div>
                {renderSheetBody(true)}
                <div className="border-t border-slate-200 pt-3 text-[11px] text-slate-400 text-center">
                  PrintBar Kiosk High-Resolution Raster Preview
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export const StepConfigure: React.FC<StepConfigureProps> = ({
  config,
  onChangeConfig,
  onBack,
  onNext,
  onRemoveFile,
}) => {
  const navigate = useNavigate();
  const [showMoreOptions, setShowMoreOptions] = useState(false);
  const [isSpecificPageModalOpen, setIsSpecificPageModalOpen] = useState(false);
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  
  const file = config.file;
  const filesList = (config.files && config.files.length > 0) ? config.files : (file ? [file] : []);
  const activeFile = filesList[activeFileIndex] || filesList[0] || file;
  const pageCount = filesList.length > 0 ? filesList.reduce((acc, f) => acc + f.pageCount, 0) : 12;
  const fileName = filesList.length > 1 ? `${filesList.length} Files (${filesList[0].name} +${filesList.length - 1} more)` : (file ? file.name : 'proposal_v2.pdf');
  const fileSizeMB = filesList.length > 0 ? (filesList.reduce((acc, f) => acc + f.size, 0) / (1024 * 1024)).toFixed(1) : '2.4';

  const pagesPerSheet = config.pagesPerSheet || '1 on 1';
  const pagesSelection = config.pagesSelection || 'all';

  // Helper to parse current selected page numbers set
  const getSelectedPagesSet = (): Set<number> => {
    if (pagesSelection === 'all' || !config.pageRange) {
      const allSet = new Set<number>();
      for (let i = 1; i <= pageCount; i++) allSet.add(i);
      return allSet;
    }
    const set = new Set<number>();
    const parts = config.pageRange.split(',');
    for (const part of parts) {
      const trimmed = part.trim();
      if (trimmed.includes('-')) {
        const [startStr, endStr] = trimmed.split('-');
        const start = parseInt(startStr, 10);
        const end = parseInt(endStr, 10);
        if (!isNaN(start) && !isNaN(end)) {
          for (let i = Math.min(start, end); i <= Math.max(start, end); i++) {
            if (i >= 1 && i <= pageCount) set.add(i);
          }
        }
      } else {
        const num = parseInt(trimmed, 10);
        if (!isNaN(num) && num >= 1 && num <= pageCount) {
          set.add(num);
        }
      }
    }
    return set;
  };

  const [modalSelectedPages, setModalSelectedPages] = useState<Set<number>>(new Set());

  const handleOpenSpecificPageModal = () => {
    setModalSelectedPages(getSelectedPagesSet());
    setIsSpecificPageModalOpen(true);
  };

  const handleToggleModalPage = (pageNum: number) => {
    setModalSelectedPages((prev) => {
      const next = new Set(prev);
      if (next.has(pageNum)) {
        next.delete(pageNum);
      } else {
        next.add(pageNum);
      }
      return next;
    });
  };

  const handleClearModalSelection = () => {
    setModalSelectedPages(new Set());
  };

  const handleConfirmModalSelection = () => {
    if (modalSelectedPages.size === pageCount) {
      onChangeConfig({ ...config, pagesSelection: 'all', pageRange: '' });
    } else {
      const sorted = Array.from<number>(modalSelectedPages).sort((a: number, b: number) => a - b);
      if (sorted.length === 0) {
        onChangeConfig({ ...config, pagesSelection: 'range', pageRange: '' });
      } else {
        // Format compressed range e.g. "1-3" or "1,3,5"
        const ranges: string[] = [];
        let start = sorted[0];
        let prev = sorted[0];

        for (let i = 1; i < sorted.length; i++) {
          if (sorted[i] === prev + 1) {
            prev = sorted[i];
          } else {
            ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
            start = sorted[i];
            prev = sorted[i];
          }
        }
        ranges.push(start === prev ? `${start}` : `${start}-${prev}`);

        onChangeConfig({
          ...config,
          pagesSelection: 'range',
          pageRange: ranges.join('-') === `1-${pageCount}` ? `1-${pageCount}` : ranges.join(','),
        });
      }
    }
    setIsSpecificPageModalOpen(false);
  };

  // Convert modal set back to formatted string input
  const getModalRangeText = (): string => {
    if (modalSelectedPages.size === 0) return '';
    const sorted = Array.from<number>(modalSelectedPages).sort((a: number, b: number) => a - b);
    const ranges: string[] = [];
    let start = sorted[0];
    let prev = sorted[0];

    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i] === prev + 1) {
        prev = sorted[i];
      } else {
        ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
        start = sorted[i];
        prev = sorted[i];
      }
    }
    ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
    return ranges.join(',');
  };

  const handleRemoveFileAndGoUpload = () => {
    if (onRemoveFile) {
      onRemoveFile();
    } else {
      onChangeConfig({ ...config, file: null, files: [] });
    }
    onBack();
  };

  const handleRemoveActiveFile = () => {
    if (filesList.length <= 1) {
      handleRemoveFileAndGoUpload();
    } else {
      const updatedFiles = filesList.filter((_, i) => i !== activeFileIndex);
      const newActiveIdx = Math.max(0, activeFileIndex - 1);
      setActiveFileIndex(newActiveIdx);
      onChangeConfig({
        ...config,
        file: updatedFiles[0],
        files: updatedFiles,
      });
    }
  };

  // ── Pricing (backend-driven, never local) ────────────────────────────────────
  const selectedPageCount = getSelectedPagesSet().size;
  const { price: backendPrice, isLoading: isPriceLoading } = usePricing(config, selectedPageCount);

  return (
    <div className="space-y-6 max-w-3xl mx-auto pb-28">
      
      {/* Premium Multi-File Document Manager */}
      {filesList.length > 0 && (
        <div className="bg-white border border-slate-200/90 rounded-3xl p-5 sm:p-6 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                <FileText className="w-5 h-5 stroke-[2.2]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-extrabold text-slate-900 font-['Outfit']">
                    Uploaded Documents
                  </h3>
                  <span className="text-[11px] font-bold bg-blue-100/70 text-blue-700 px-2.5 py-0.5 rounded-full">
                    {filesList.length} {filesList.length === 1 ? 'file' : 'files'} • {pageCount} {pageCount === 1 ? 'page' : 'pages'} total
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-normal mt-0.5">
                  Select a document to preview and adjust settings
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-1.5 text-xs font-extrabold text-[#0067ff] hover:text-blue-700 bg-blue-50/80 hover:bg-blue-100 border border-blue-200/60 px-4 py-2 rounded-xl transition-all cursor-pointer shadow-2xs active:scale-95 shrink-0"
            >
              <span>+ Add / Manage Files</span>
            </button>
          </div>

          {/* Document Tabs Container — Never collapses, smoothly scrolls */}
          <div className="flex items-center gap-3 overflow-x-auto pt-1 pb-2 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
            {filesList.map((f, idx) => {
              const isSelected = activeFileIndex === idx;
              const ext = f.name.includes('.') ? f.name.split('.').pop()?.toUpperCase() || 'PDF' : 'PDF';

              const handleRemoveThisFile = (e: React.MouseEvent) => {
                e.stopPropagation();
                if (filesList.length <= 1) {
                  handleRemoveFileAndGoUpload();
                } else {
                  const updatedFiles = filesList.filter((_, i) => i !== idx);
                  const newIdx = idx >= updatedFiles.length ? updatedFiles.length - 1 : idx;
                  setActiveFileIndex(newIdx);
                  onChangeConfig({
                    ...config,
                    file: updatedFiles[0],
                    files: updatedFiles,
                  });
                }
              };

              return (
                <div
                  key={f.id || idx}
                  onClick={() => setActiveFileIndex(idx)}
                  className={`group relative flex items-center justify-between gap-3 px-4 py-3 rounded-2xl text-xs font-bold transition-all cursor-pointer border min-w-[210px] max-w-[280px] shrink-0 select-none ${
                    isSelected
                      ? 'bg-gradient-to-r from-blue-600 to-[#0067ff] text-white border-transparent shadow-md shadow-blue-500/25 scale-[1.02]'
                      : 'bg-slate-50/90 border-slate-200/80 text-slate-700 hover:bg-slate-100/90 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <span className={`text-[9px] font-black px-1.5 py-0.5 rounded-md uppercase tracking-wider shrink-0 ${
                      isSelected ? 'bg-white/20 text-white' : 'bg-slate-200/80 text-slate-600'
                    }`}>
                      {ext}
                    </span>
                    <span className="truncate font-bold leading-tight" title={f.name}>
                      {f.name}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full ${
                      isSelected ? 'bg-white/25 text-white' : 'bg-slate-200/70 text-slate-600'
                    }`}>
                      {f.pageCount}p
                    </span>

                    {/* Delete X button directly on tab */}
                    <button
                      type="button"
                      onClick={handleRemoveThisFile}
                      className={`w-5 h-5 rounded-full flex items-center justify-center transition-colors ${
                        isSelected
                          ? 'hover:bg-white/30 text-white/90 hover:text-white'
                          : 'hover:bg-red-100 text-slate-400 hover:text-red-600'
                      }`}
                      title="Remove this document"
                    >
                      <X className="w-3 h-3 stroke-[2.5]" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Interactive Document File Preview */}
      <DocumentPreviewCard 
        file={activeFile} 
        colorMode={config.colorMode} 
        pagesPerSheet={config.pagesPerSheet} 
        orientation={config.orientation}
        onRemoveFile={handleRemoveActiveFile}
      />

      {/* Configuration Options Card */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 sm:p-7 shadow-xs space-y-6">
            
            {/* 1. Number of Copies */}
            <div className="flex items-center justify-between pb-5 border-b border-slate-100">
              <span className="text-base font-bold text-slate-900">Number of Copies</span>
              <div className="inline-flex items-center gap-2 bg-[#0067ff] text-white px-3.5 py-1.5 rounded-xl shadow-xs">
                <button
                  type="button"
                  onClick={() => onChangeConfig({ ...config, copies: Math.max(1, config.copies - 1) })}
                  className="w-6 h-6 flex items-center justify-center rounded-lg hover:bg-white/20 font-bold text-lg cursor-pointer transition-colors"
                >
                  -
                </button>
                <span className="font-extrabold text-base px-2 min-w-[20px] text-center">{config.copies}</span>
                <button
                  type="button"
                  onClick={() => onChangeConfig({ ...config, copies: Math.min(50, config.copies + 1) })}
                  className="w-6 h-6 flex items-center justify-center rounded-lg hover:bg-white/20 font-bold text-lg cursor-pointer transition-colors"
                >
                  +
                </button>
              </div>
            </div>

            {/* 2. Color Mode */}
            <div className="space-y-3 pb-5 border-b border-slate-100">
              <h4 className="text-base font-bold text-slate-900">Color Mode</h4>
              <div className="grid grid-cols-2 gap-3 sm:gap-4">
                {/* B/W Option */}
                <button
                  type="button"
                  onClick={() => onChangeConfig({ ...config, colorMode: 'bw' })}
                  className={`rounded-2xl p-4 flex items-center justify-between transition-all cursor-pointer ${
                    config.colorMode === 'bw'
                      ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                      : 'bg-white border border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="text-left">
                    <span className={`block font-bold text-base ${config.colorMode === 'bw' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                      B/W
                    </span>
                    <span className="block text-xs text-slate-400 font-medium">₹2/page</span>
                  </div>
                  {/* B/W Venn diagram circles */}
                  <div className="relative w-8 h-8 shrink-0">
                    <div className="absolute top-0 left-0 w-4.5 h-4.5 rounded-full bg-slate-700/80 mix-blend-multiply" />
                    <div className="absolute top-0 right-0 w-4.5 h-4.5 rounded-full bg-slate-900/90 mix-blend-multiply" />
                    <div className="absolute bottom-0 left-2 w-4.5 h-4.5 rounded-full bg-slate-500/80 mix-blend-multiply" />
                  </div>
                </button>

                {/* Color Option */}
                <button
                  type="button"
                  onClick={() => onChangeConfig({ ...config, colorMode: 'color' })}
                  className={`rounded-2xl p-4 flex items-center justify-between transition-all cursor-pointer ${
                    config.colorMode === 'color'
                      ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                      : 'bg-white border border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="text-left">
                    <span className={`block font-bold text-base ${config.colorMode === 'color' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                      Color
                    </span>
                    <span className="block text-xs text-slate-400 font-medium">₹10/page</span>
                  </div>
                  {/* CMYK overlapping circles */}
                  <div className="relative w-8 h-8 shrink-0">
                    <div className="absolute top-0 left-0 w-4.5 h-4.5 rounded-full bg-cyan-500/90" />
                    <div className="absolute top-0 right-0 w-4.5 h-4.5 rounded-full bg-fuchsia-600/90" />
                    <div className="absolute bottom-0 left-2 w-4.5 h-4.5 rounded-full bg-amber-400/95" />
                  </div>
                </button>
              </div>
            </div>

            {/* 3. Duplex (Layout) */}
            <div className="space-y-3 pb-5 border-b border-slate-100">
              <h4 className="text-base font-bold text-slate-900">Duplex (Layout)</h4>
              <div className="grid grid-cols-2 gap-3 sm:gap-4">
                {/* 1-sided Option */}
                <button
                  type="button"
                  onClick={() => onChangeConfig({ ...config, duplex: false })}
                  className={`rounded-2xl p-4 flex items-center justify-between transition-all cursor-pointer ${
                    !config.duplex
                      ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                      : 'bg-white border border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <span className={`font-bold text-base ${!config.duplex ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                    1-sided
                  </span>
                  <div className={`p-1.5 rounded-xl border ${!config.duplex ? 'border-[#0067ff] text-[#0067ff]' : 'border-slate-300 text-slate-500'}`}>
                    <FileText className="w-4 h-4 stroke-[2]" />
                  </div>
                </button>

                {/* 2-sided Option (Disabled) */}
                <button
                  type="button"
                  disabled
                  className="rounded-2xl p-4 flex items-center justify-between bg-slate-50/70 border border-slate-200/80 cursor-not-allowed opacity-60"
                  title="2-sided printing unavailable"
                >
                  <span className="font-bold text-base text-slate-400">
                    2-sided
                  </span>
                  <div className="p-1.5 rounded-xl border border-slate-200 text-slate-300">
                    <FileText className="w-4 h-4 stroke-[2]" />
                  </div>
                </button>
              </div>
            </div>

            {/* 4. Orientation */}
            <div className="space-y-3">
              <h4 className="text-base font-bold text-slate-900">Orientation</h4>
              <div className="grid grid-cols-2 gap-3 sm:gap-4">
                {/* Portrait Option */}
                <button
                  type="button"
                  onClick={() => onChangeConfig({ ...config, orientation: 'portrait' })}
                  className={`rounded-2xl p-4 flex items-center justify-between transition-all cursor-pointer ${
                    config.orientation === 'portrait'
                      ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                      : 'bg-white border border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <span className={`font-bold text-base ${config.orientation === 'portrait' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                    Portrait
                  </span>
                  <div className={`p-1.5 rounded-xl border ${config.orientation === 'portrait' ? 'border-[#0067ff] text-[#0067ff]' : 'border-slate-300 text-slate-500'}`}>
                    <div className="w-4 h-5 rounded-xs border-2 border-current flex flex-col justify-center gap-0.5 p-0.5">
                      <div className="w-full h-0.5 bg-current rounded-xs" />
                      <div className="w-full h-0.5 bg-current rounded-xs" />
                    </div>
                  </div>
                </button>

                {/* Landscape Option */}
                <button
                  type="button"
                  onClick={() => onChangeConfig({ ...config, orientation: 'landscape' })}
                  className={`rounded-2xl p-4 flex items-center justify-between transition-all cursor-pointer ${
                    config.orientation === 'landscape'
                      ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                      : 'bg-white border border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <span className={`font-bold text-base ${config.orientation === 'landscape' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                    Landscape
                  </span>
                  <div className={`p-1.5 rounded-xl border ${config.orientation === 'landscape' ? 'border-[#0067ff] text-[#0067ff]' : 'border-slate-300 text-slate-500'}`}>
                    <div className="w-5 h-4 rounded-xs border-2 border-current flex flex-col justify-center gap-0.5 p-0.5">
                      <div className="w-full h-0.5 bg-current rounded-xs" />
                      <div className="w-full h-0.5 bg-current rounded-xs" />
                    </div>
                  </div>
                </button>
              </div>
            </div>

            {/* 5. More Options Button */}
            <div className="pt-2">
              <button
                type="button"
                onClick={() => setShowMoreOptions(!showMoreOptions)}
                className="w-full py-3.5 px-4 bg-slate-50 hover:bg-slate-100/90 active:bg-slate-200/80 border border-slate-200/90 rounded-2xl flex items-center justify-center gap-2.5 transition-all cursor-pointer shadow-2xs group"
              >
                <Settings className="w-4.5 h-4.5 text-slate-700 group-hover:rotate-45 transition-transform duration-300 stroke-[2]" />
                <span className="font-bold text-slate-900 text-base">
                  More Options
                </span>
                <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform duration-200 ${showMoreOptions ? 'rotate-180' : ''}`} />
              </button>
            </div>

            {/* Expanded More Options Panel (Pages Per Sheet & Pages Selection) */}
            {showMoreOptions && (
              <div className="space-y-6 pt-4 border-t border-slate-100 animate-fadeIn">
                
                {/* Pages Per Sheet */}
                <div className="space-y-3">
                  <h4 className="text-base font-bold text-slate-900">Pages Per Sheet</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3">
                    
                    {/* 1 on 1 */}
                    <button
                      type="button"
                      onClick={() => onChangeConfig({ ...config, pagesPerSheet: '1 on 1' })}
                      className={`rounded-xl py-3 px-2 flex items-center justify-center transition-all cursor-pointer ${
                        pagesPerSheet === '1 on 1'
                          ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                          : 'bg-white border border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <span className={`font-bold text-sm ${pagesPerSheet === '1 on 1' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                        1 on 1
                      </span>
                    </button>

                    {/* 2 on 1 */}
                    <button
                      type="button"
                      onClick={() => onChangeConfig({ ...config, pagesPerSheet: '2 on 1' })}
                      className={`rounded-xl py-3 px-2 flex items-center justify-center transition-all cursor-pointer ${
                        pagesPerSheet === '2 on 1'
                          ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                          : 'bg-white border border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <span className={`font-bold text-sm ${pagesPerSheet === '2 on 1' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                        2 on 1
                      </span>
                    </button>

                    {/* 4 on 1 */}
                    <button
                      type="button"
                      onClick={() => onChangeConfig({ ...config, pagesPerSheet: '4 on 1' })}
                      className={`rounded-xl py-3 px-2 flex items-center justify-center transition-all cursor-pointer ${
                        pagesPerSheet === '4 on 1'
                          ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                          : 'bg-white border border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <span className={`font-bold text-sm ${pagesPerSheet === '4 on 1' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                        4 on 1
                      </span>
                    </button>

                    {/* 6 on 1 */}
                    <button
                      type="button"
                      onClick={() => onChangeConfig({ ...config, pagesPerSheet: '6 on 1' })}
                      className={`rounded-xl py-3 px-2 flex items-center justify-center transition-all cursor-pointer ${
                        pagesPerSheet === '6 on 1'
                          ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                          : 'bg-white border border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <span className={`font-bold text-sm ${pagesPerSheet === '6 on 1' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                        6 on 1
                      </span>
                    </button>

                  </div>
                </div>

                {/* Pages Selection */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <h4 className="text-base font-bold text-slate-900">Pages Selection</h4>
                    <div className="group relative cursor-pointer flex items-center">
                      <div className="w-4.5 h-4.5 rounded-full border border-slate-400 text-slate-500 flex items-center justify-center text-[10px] font-bold hover:bg-slate-100 transition-colors">
                        i
                      </div>
                      <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:block w-52 bg-slate-900 text-white text-[11px] font-medium p-2 rounded-lg shadow-lg z-20 text-center">
                        Select all pages or enter custom range (e.g. 1-5, 8).
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 sm:gap-4">
                    {/* All Option */}
                    <button
                      type="button"
                      onClick={() => onChangeConfig({ ...config, pagesSelection: 'all' })}
                      className={`rounded-2xl p-4 flex items-center justify-center transition-all cursor-pointer ${
                        pagesSelection === 'all'
                          ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                          : 'bg-white border border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <span className={`font-bold text-base ${pagesSelection === 'all' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                        All
                      </span>
                    </button>

                    {/* Range Option */}
                    <button
                      type="button"
                      onClick={() => {
                        onChangeConfig({ ...config, pagesSelection: 'range', pageRange: config.pageRange || `1-${Math.min(3, pageCount)}` });
                        handleOpenSpecificPageModal();
                      }}
                      className={`rounded-2xl p-4 flex items-center justify-center transition-all cursor-pointer ${
                        pagesSelection === 'range'
                          ? 'bg-[#e8f2ff] border-2 border-[#0067ff] shadow-xs'
                          : 'bg-white border border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <span className={`font-bold text-base ${pagesSelection === 'range' ? 'text-[#0067ff]' : 'text-slate-800'}`}>
                        Range
                      </span>
                    </button>
                  </div>

                  {/* Range Input Field */}
                  {pagesSelection === 'range' && (
                    <div className="pt-2 animate-fadeIn space-y-1.5">
                      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 max-w-full">
                        <input
                          type="text"
                          value={config.pageRange || ''}
                          onClick={handleOpenSpecificPageModal}
                          readOnly
                          placeholder="e.g. 1-3"
                          className="flex-1 min-w-0 h-9 sm:h-10 border border-slate-200 focus:border-[#0067ff] rounded-lg px-3 py-1.5 text-xs sm:text-sm text-slate-900 bg-white outline-none cursor-pointer font-bold shadow-2xs transition-all"
                        />
                        <button
                          type="button"
                          onClick={handleOpenSpecificPageModal}
                          className="bg-[#0067ff] hover:bg-[#0052cc] text-white font-bold text-xs px-3.5 h-9 sm:h-10 rounded-lg transition-all cursor-pointer shrink-0 shadow-2xs flex items-center justify-center gap-1.5 active:scale-95 whitespace-nowrap"
                        >
                          <FileText className="w-3.5 h-3.5 shrink-0 text-white" />
                          <span>Select Specific Pages</span>
                        </button>
                      </div>
                      <p className="text-[11px] text-slate-500 font-normal">
                        Click 'Select Specific Pages' or the range field to view and pick pages visually.
                      </p>
                    </div>
                  )}

                </div>

              </div>
            )}

          </div>

      {/* STICKY BOTTOM ACTION BAR */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200/80 shadow-[0_-4px_20px_rgba(0,0,0,0.08)] z-50 px-4 py-3 sm:px-8">
        <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
          <div>
            <span className="block text-slate-500 font-medium text-xs sm:text-sm">
              {selectedPageCount} {selectedPageCount === 1 ? 'page' : 'pages'} × {config.copies} {config.copies === 1 ? 'copy' : 'copies'} — {config.colorMode === 'bw' ? '₹2/page' : '₹10/page'}
            </span>
            {isPriceLoading ? (
              <span className="flex items-center gap-1.5 mt-0.5">
                <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
                <span className="text-slate-400 font-bold text-xl">Calculating...</span>
              </span>
            ) : backendPrice ? (
              <span className="block text-slate-900 font-black text-xl sm:text-2xl leading-none mt-0.5">
                ₹{Number(backendPrice.totalInr).toFixed(0)}
                <span className="ml-2 text-xs font-medium text-slate-400">
                  All-inclusive
                </span>
              </span>
            ) : (
              <span className="block text-slate-900 font-black text-xl sm:text-2xl leading-none mt-0.5">
                ₹—
              </span>
            )}
          </div>


          <button
            type="button"
            onClick={onNext}
            className="bg-[#0067ff] hover:bg-[#0052cc] text-white font-bold text-base sm:text-lg px-8 py-3.5 rounded-full shadow-md transition-all cursor-pointer hover:shadow-lg active:scale-98"
          >
            Proceed To Pay
          </button>
        </div>
      </div>

      {/* SPECIFIC PAGE SELECTION MODAL */}
      {isSpecificPageModalOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-50 flex items-end justify-center sm:items-center sm:p-4 animate-fadeIn"
          onClick={() => setIsSpecificPageModalOpen(false)}
        >
          <div 
            className="bg-white w-full max-w-md sm:max-w-lg rounded-t-3xl sm:rounded-3xl max-h-[88vh] flex flex-col overflow-hidden shadow-2xl transition-all border border-slate-100"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Top Handle bar */}
            <div className="pt-2.5 pb-1 flex justify-center">
              <div className="w-12 h-1.5 bg-slate-300 rounded-full" />
            </div>

            {/* Modal Header */}
            <div className="px-6 py-3 flex items-center justify-between border-b border-slate-100">
              <div className="flex items-center gap-2">
                <h3 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                  Specific Page
                </h3>
                <div className="w-5 h-5 rounded-full border border-slate-400 text-slate-600 flex items-center justify-center text-xs font-bold">
                  i
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsSpecificPageModalOpen(false)}
                className="w-9 h-9 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center transition-colors cursor-pointer"
              >
                <X className="w-5 h-5 stroke-[2.5]" />
              </button>
            </div>

            {/* Input & Clear Row */}
            <div className="px-4 sm:px-6 pt-3 pb-2 flex items-center gap-2">
              <input
                type="text"
                value={getModalRangeText()}
                onChange={(e) => {
                  const val = e.target.value;
                  const set = new Set<number>();
                  const parts = val.split(',');
                  for (const part of parts) {
                    const trimmed = part.trim();
                    if (trimmed.includes('-')) {
                      const [startStr, endStr] = trimmed.split('-');
                      const start = parseInt(startStr, 10);
                      const end = parseInt(endStr, 10);
                      if (!isNaN(start) && !isNaN(end)) {
                        for (let i = Math.min(start, end); i <= Math.max(start, end); i++) {
                          if (i >= 1 && i <= pageCount) set.add(i);
                        }
                      }
                    } else {
                      const num = parseInt(trimmed, 10);
                      if (!isNaN(num) && num >= 1 && num <= pageCount) set.add(num);
                    }
                  }
                  setModalSelectedPages(set);
                }}
                placeholder="e.g. 1-3"
                className="flex-1 h-10 border border-slate-200 focus:border-[#0067ff] focus:ring-2 focus:ring-[#0067ff]/20 rounded-xl px-3 py-2 text-sm font-bold text-slate-900 bg-white outline-none shadow-2xs transition-all"
              />
              <button
                type="button"
                onClick={handleClearModalSelection}
                className="h-10 border-2 border-red-500 text-red-500 font-bold text-xs sm:text-sm px-4 rounded-xl hover:bg-red-50 active:scale-95 transition-all cursor-pointer shrink-0 flex items-center justify-center"
              >
                Clear
              </button>
            </div>

            {/* Page Thumbnails Grid */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-2">
              <div className="grid grid-cols-2 gap-3 sm:gap-4 pb-4">
                {Array.from({ length: pageCount }, (_, i) => i + 1).map((pageNum) => {
                  const isSelected = modalSelectedPages.has(pageNum);
                  return (
                    <div
                      key={pageNum}
                      onClick={() => handleToggleModalPage(pageNum)}
                      className={`relative rounded-xl sm:rounded-2xl transition-all cursor-pointer overflow-hidden flex flex-col justify-between bg-white h-48 sm:h-52 border-2 ${
                        isSelected
                          ? 'border-[#0067ff] ring-1 ring-[#0067ff]/20 shadow-xs'
                          : 'border-slate-200/90 hover:border-slate-300'
                      }`}
                    >
                      {/* Check badge top right */}
                      <div className="absolute top-3 right-3 z-20">
                        {isSelected ? (
                          <div className="w-7 h-7 rounded-full bg-[#0067ff] text-white flex items-center justify-center shadow-xs">
                            <Check className="w-4 h-4 stroke-[3]" />
                          </div>
                        ) : (
                          <div className="w-7 h-7 rounded-full border-2 border-slate-300 bg-white/90" />
                        )}
                      </div>

                      {/* Page Thumbnail Preview */}
                      <div className="flex-1 p-2 flex items-center justify-center overflow-hidden bg-slate-50/40">
                        <PagePreviewCell
                          file={file}
                          pageNum={pageNum}
                          totalPageCount={pageCount}
                          colorMode={config.colorMode}
                          isCompact={true}
                        />
                      </div>

                      {/* Card Footer Page Tag */}
                      <div className="py-2.5 bg-slate-100/80 text-center font-extrabold text-slate-900 text-sm border-t border-slate-200/60">
                        Page {pageNum}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Modal Bottom Sticky Confirm Button */}
            <div className="p-4 sm:p-5 border-t border-slate-100 bg-white">
              <button
                type="button"
                onClick={handleConfirmModalSelection}
                className="w-full bg-[#0067ff] hover:bg-[#0052cc] text-white font-extrabold text-lg py-3.5 sm:py-4 rounded-2xl shadow-md transition-all active:scale-98 cursor-pointer text-center"
              >
                Confirm
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};
