import React, { useState } from 'react';
import { PRINTER_HUBS } from '../data/mockData';
import { PrinterHub } from '../types';
import { 
  MapPin, 
  Printer, 
  Clock, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle,
  Filter,
  Navigation,
  Sparkles,
  Layers
} from 'lucide-react';

interface LocationsViewProps {
  onSelectHubAndPrint: (hubId: string) => void;
}

export const LocationsView: React.FC<LocationsViewProps> = ({
  onSelectHubAndPrint,
}) => {
  const [filter24h, setFilter24h] = useState(false);
  const [filterColor, setFilterColor] = useState(false);
  const [filterA3, setFilterA3] = useState(false);

  const filteredHubs = PRINTER_HUBS.filter((hub) => {
    if (filter24h && !hub.is24Hours) return false;
    if (filterColor && !hub.colorAvailable) return false;
    if (filterA3 && !hub.a3Available) return false;
    return true;
  });

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
      
      {/* Header */}
      <div className="space-y-2 text-center md:text-left">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-semibold">
          <MapPin className="w-3.5 h-3.5" />
          <span>Interactive Station Finder</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold font-['Outfit'] text-white">
          Nearby PrintBar Kiosk Terminals
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 max-w-2xl">
          Locate self-service printing hubs, monitor paper & toner levels in real-time, and route print jobs instantly.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl flex flex-wrap items-center justify-between gap-4">
        
        <div className="flex items-center gap-2 text-xs text-slate-400 font-bold uppercase tracking-wider">
          <Filter className="w-4 h-4 text-cyan-400" />
          <span>Filter Stations:</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setFilter24h(!filter24h)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border cursor-pointer ${
              filter24h
                ? 'bg-cyan-500 text-slate-950 border-cyan-400'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
            }`}
          >
            🌙 Open 24/7
          </button>

          <button
            onClick={() => setFilterColor(!filterColor)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border cursor-pointer ${
              filterColor
                ? 'bg-cyan-500 text-slate-950 border-cyan-400'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
            }`}
          >
            🎨 Color Available
          </button>

          <button
            onClick={() => setFilterA3(!filterA3)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border cursor-pointer ${
              filterA3
                ? 'bg-cyan-500 text-slate-950 border-cyan-400'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
            }`}
          >
            📐 A3 Poster Paper
          </button>
        </div>

        <span className="text-xs text-slate-400 font-mono">
          Showing <strong>{filteredHubs.length}</strong> of {PRINTER_HUBS.length} stations
        </span>

      </div>

      {/* Stations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredHubs.map((hub) => (
          <div
            key={hub.id}
            className={`bg-slate-900/90 border rounded-3xl p-6 space-y-5 transition-all duration-200 flex flex-col justify-between ${
              hub.status === 'online'
                ? 'border-slate-800 hover:border-cyan-500/50 shadow-xl hover:shadow-cyan-950/20'
                : hub.status === 'warning'
                ? 'border-amber-500/30 bg-amber-950/10'
                : 'border-red-500/30 bg-red-950/10 opacity-75'
            }`}
          >
            {/* Top Card Info */}
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-2.5 h-2.5 rounded-full ${
                      hub.status === 'online' ? 'bg-emerald-400 animate-pulse' : hub.status === 'warning' ? 'bg-amber-400' : 'bg-red-500'
                    }`} />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      {hub.status.toUpperCase()}
                    </span>
                  </div>
                  <h3 className="font-bold text-base text-white leading-snug">
                    {hub.name}
                  </h3>
                </div>

                <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-cyan-400 text-xs font-mono font-bold shrink-0">
                  {hub.distanceKm} km
                </span>
              </div>

              <p className="text-xs text-slate-400 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                <span>{hub.address}, {hub.city}</span>
              </p>

              {/* Station Capability Badges */}
              <div className="flex flex-wrap gap-1.5 text-[10px] font-semibold">
                {hub.is24Hours && (
                  <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                    24/7 Access
                  </span>
                )}
                <span className="px-2 py-0.5 rounded bg-slate-950 text-slate-300 border border-slate-800">
                  {hub.colorAvailable ? 'Color & B&W' : 'B&W Only'}
                </span>
                {hub.a3Available && (
                  <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                    A3 Format
                  </span>
                )}
              </div>
            </div>

            {/* Middle: Hardware Gauges */}
            <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800 space-y-3">
              <div className="space-y-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span>Paper Reservoir:</span>
                  <span className={hub.paperLevel < 20 ? 'text-amber-400 font-bold' : 'text-emerald-400'}>
                    {hub.paperLevel}% Capacity
                  </span>
                </div>
                <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      hub.paperLevel < 20 ? 'bg-amber-400' : 'bg-emerald-400'
                    }`}
                    style={{ width: `${hub.paperLevel}%` }}
                  />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span>CMYK Toner Drum:</span>
                  <span className="text-cyan-400">{hub.tonerLevel}% Level</span>
                </div>
                <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-cyan-400 rounded-full"
                    style={{ width: `${hub.tonerLevel}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-900">
                <span>Active Queue: <strong className="text-white">{hub.currentQueue} job(s)</strong></span>
                <span>Today: <strong className="text-white">{hub.completedToday} prints</strong></span>
              </div>
            </div>

            {/* Bottom Action Button */}
            <button
              disabled={hub.status === 'offline'}
              onClick={() => onSelectHubAndPrint(hub.id)}
              className={`w-full py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer ${
                hub.status !== 'offline'
                  ? 'bg-gradient-to-r from-cyan-400 to-cyan-500 text-slate-950 hover:from-cyan-300 hover:to-cyan-400 shadow-md shadow-cyan-500/20'
                  : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              }`}
            >
              <Printer className="w-4 h-4" />
              <span>{hub.status !== 'offline' ? 'Send Print To This Hub' : 'Station Under Maintenance'}</span>
            </button>

          </div>
        ))}
      </div>

    </div>
  );
};
