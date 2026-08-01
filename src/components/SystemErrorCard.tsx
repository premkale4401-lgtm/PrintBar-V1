import React from 'react';
import { SystemErrorType } from '../types';
import { 
  Printer, 
  CreditCard, 
  FileText, 
  WifiOff, 
  CloudOff, 
  FileX, 
  RotateCw,
  Slash
} from 'lucide-react';

interface SystemErrorCardProps {
  type: SystemErrorType;
  onPrimaryAction?: () => void;
  onSecondaryAction?: () => void;
  className?: string;
}

export const ERROR_DETAILS: Record<SystemErrorType, {
  title: string;
  description: string;
  primaryButtonText: string;
  secondaryButtonText: string;
  hasRefreshIcon?: boolean;
  bgCircleClass: string;
  iconColorClass: string;
}> = {
  hardware_disconnected: {
    title: 'Hardware Disconnected',
    description: "We can't reach the printer right now. Please check the physical connection.",
    primaryButtonText: 'Retry Connection',
    secondaryButtonText: 'Contact Support',
    bgCircleClass: 'bg-red-50/80 border border-red-100',
    iconColorClass: 'text-red-500',
  },
  transaction_declined: {
    title: 'Transaction Declined',
    description: 'Your bank or card issuer declined the payment. Please verify your details.',
    primaryButtonText: 'Try Another Method',
    secondaryButtonText: 'Check Billing History',
    bgCircleClass: 'bg-red-50/80 border border-red-100',
    iconColorClass: 'text-red-500',
  },
  out_of_paper: {
    title: 'Out of Paper',
    description: 'The printer at Main St. Digital Hub is out of paper.',
    primaryButtonText: 'Notify Attendant',
    secondaryButtonText: 'Refresh status',
    hasRefreshIcon: true,
    bgCircleClass: 'bg-slate-100 border border-slate-200/60',
    iconColorClass: 'text-slate-700',
  },
  connection_lost: {
    title: 'Connection Lost',
    description: 'Check your internet connection and try again. The server is currently unreachable.',
    primaryButtonText: 'Retry Now',
    secondaryButtonText: 'Check Network Settings',
    bgCircleClass: 'bg-red-50/80 border border-red-100',
    iconColorClass: 'text-red-500',
  },
  transmission_interrupted: {
    title: 'Transmission Interrupted',
    description: 'Something went wrong during the upload. Your progress has been saved locally.',
    primaryButtonText: 'Resume Upload',
    secondaryButtonText: 'Cancel Transfer',
    bgCircleClass: 'bg-blue-50/80 border border-blue-100',
    iconColorClass: 'text-blue-500',
  },
  file_size_exceeded: {
    title: 'File Size Exceeded',
    description: 'Maximum file size is 50MB. Your document is currently 62MB.',
    primaryButtonText: 'Back to Upload',
    secondaryButtonText: 'View Compression Tips',
    bgCircleClass: 'bg-red-50/80 border border-red-100',
    iconColorClass: 'text-red-500',
  },
};

export const SystemErrorCard: React.FC<SystemErrorCardProps> = ({
  type,
  onPrimaryAction,
  onSecondaryAction,
  className = '',
}) => {
  const details = ERROR_DETAILS[type];

  const renderIcon = () => {
    switch (type) {
      case 'hardware_disconnected':
        return (
          <div className="relative">
            <Printer className="w-7 h-7 stroke-[2]" />
            <Slash className="w-7 h-7 stroke-[2.5] absolute inset-0 text-red-600" />
          </div>
        );
      case 'transaction_declined':
        return (
          <div className="relative">
            <CreditCard className="w-7 h-7 stroke-[2]" />
            <Slash className="w-7 h-7 stroke-[2.5] absolute inset-0 text-red-600" />
          </div>
        );
      case 'out_of_paper':
        return (
          <div className="relative">
            <FileText className="w-7 h-7 stroke-[2]" />
            <Slash className="w-7 h-7 stroke-[2.5] absolute inset-0 text-slate-800" />
          </div>
        );
      case 'connection_lost':
        return <WifiOff className="w-7 h-7 stroke-[2]" />;
      case 'transmission_interrupted':
        return <CloudOff className="w-7 h-7 stroke-[2]" />;
      case 'file_size_exceeded':
        return (
          <div className="relative">
            <FileX className="w-7 h-7 stroke-[2]" />
          </div>
        );
      default:
        return <FileX className="w-7 h-7 stroke-[2]" />;
    }
  };

  return (
    <div className={`bg-white border border-slate-200/80 rounded-3xl p-7 flex flex-col items-center text-center shadow-xs space-y-4 transition-all hover:shadow-md ${className}`}>
      
      {/* Icon Circle */}
      <div className={`w-16 h-16 rounded-full flex items-center justify-center shrink-0 ${details.bgCircleClass} ${details.iconColorClass}`}>
        {renderIcon()}
      </div>

      {/* Title & Description */}
      <div className="space-y-1.5 max-w-xs">
        <h3 className="text-lg font-bold font-['Outfit'] text-slate-900 tracking-tight">
          {details.title}
        </h3>
        <p className="text-xs text-slate-500 font-normal leading-relaxed">
          {details.description}
        </p>
      </div>

      {/* Primary Action Button */}
      <button
        type="button"
        onClick={onPrimaryAction}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs py-3 rounded-xl cursor-pointer transition-colors shadow-xs active:scale-95 mt-2"
      >
        {details.primaryButtonText}
      </button>

      {/* Secondary Action Link */}
      <button
        type="button"
        onClick={onSecondaryAction}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 cursor-pointer transition-colors pt-0.5"
      >
        {details.hasRefreshIcon && <RotateCw className="w-3.5 h-3.5 text-slate-500" />}
        <span>{details.secondaryButtonText}</span>
      </button>

    </div>
  );
};
