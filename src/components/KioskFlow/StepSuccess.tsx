import React from 'react';
import { PrintConfig } from '../../types';
import { 
  Check, 
  Info, 
  Printer, 
  Home
} from 'lucide-react';

interface StepSuccessProps {
  config: PrintConfig;
  onPrintAnother: () => void;
  onGoHome: () => void;
}

export const StepSuccess: React.FC<StepSuccessProps> = ({
  config,
  onPrintAnother,
  onGoHome,
}) => {
  const file = config.file;
  const pageCount = file ? file.pageCount : 12;

  return (
    <div className="space-y-6 max-w-lg mx-auto text-center pb-12 pt-4">
      
      {/* 1. MINT GREEN CIRCLE CHECKMARK BADGE */}
      <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
        <Check className="w-8 h-8 stroke-[3]" />
      </div>

      {/* 2. HEADLINE & SUBTITLE */}
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold font-['Outfit'] text-slate-900 tracking-tight">
          Printed Successfully
        </h1>
        <p className="text-sm text-slate-500 font-normal max-w-sm mx-auto">
          Your high-precision document has been dispatched to the printer.
        </p>
      </div>

      {/* 3. RECEIPT CARD */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs space-y-4 text-left">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500 font-medium">Job ID</span>
          <span className="font-bold text-slate-900 font-mono">PF-8829-10</span>
        </div>

        <div className="border-t border-slate-100 pt-4 flex items-center justify-between text-sm">
          <span className="text-slate-500 font-medium">Pages Printed</span>
          <span className="font-bold text-slate-900">{pageCount} Pages</span>
        </div>

        <div className="border-t border-slate-100 pt-4 flex items-center justify-between text-sm">
          <span className="text-slate-500 font-medium">Amount Paid</span>
          <span className="font-bold text-blue-600">$1.44</span>
        </div>
      </div>

      {/* 4. COLLECTION INSTRUCTIONS CALLOUT */}
      <div className="bg-blue-50/70 border border-blue-100/80 rounded-2xl p-4 flex items-start gap-3 text-xs text-slate-600 text-left leading-relaxed">
        <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-slate-900">Collection Instructions: </span>
          <span>
            Your document is ready for pickup at <strong className="text-blue-600 font-semibold">Main St. Digital Hub</strong>. Please show your digital receipt to the attendant.
          </span>
        </div>
      </div>

      {/* 5. ACTION BUTTONS */}
      <div className="space-y-3 pt-2">
        <button
          onClick={onPrintAnother}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm py-3.5 rounded-xl flex items-center justify-center gap-2 cursor-pointer transition-colors shadow-xs active:scale-95"
        >
          <Printer className="w-4 h-4" />
          <span>Print Another Document</span>
        </button>

        <button
          onClick={onGoHome}
          className="w-full bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 font-semibold text-sm py-3 rounded-xl flex items-center justify-center gap-2 cursor-pointer transition-colors"
        >
          <Home className="w-4 h-4 text-slate-500" />
          <span>Return Home</span>
        </button>
      </div>

    </div>
  );
};
