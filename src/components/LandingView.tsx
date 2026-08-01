import React, { useState } from 'react';
import { PrintBarLogo } from './PrintBarLogo';
import { 
  Zap, 
  Shield, 
  CreditCard, 
  Trash2, 
  Play, 
  ArrowRight,
  QrCode,
  Github,
  Twitter,
  Printer,
  Sparkles
} from 'lucide-react';
import kioskImage from '../assets/images/regenerated_image_1785591443409.png';
import kioskExplodedViewPhoto from '../assets/images/printbar_kiosk_exploded_view.jpg';

interface LandingViewProps {
  onStartKioskFlow: (hubId?: string) => void;
  onSelectHubs: () => void;
  onOpenDiagnostics: () => void;
}

const InteractiveKioskImage: React.FC = () => {
  const [transform, setTransform] = useState({ rotateX: 0, rotateY: 0, scale: 1, glowX: 50, glowY: 50 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    // Gentle, subtle tilt angles (max 5 degrees)
    const rotateX = -((y - centerY) / centerY) * 5;
    const rotateY = ((x - centerX) / centerX) * 5;

    const glowX = (x / rect.width) * 100;
    const glowY = (y / rect.height) * 100;

    setTransform({ rotateX, rotateY, scale: 1.015, glowX, glowY });
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setTransform({ rotateX: 0, rotateY: 0, scale: 1, glowX: 50, glowY: 50 });
  };

  return (
    <div 
      className="relative group cursor-pointer max-w-xs sm:max-w-sm lg:max-w-md mx-auto w-full"
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{ perspective: '1200px' }}
    >
      {/* Soft Glow Ambient Aura */}
      <div 
        className="absolute -inset-3 rounded-3xl bg-gradient-to-r from-blue-600/20 via-indigo-500/15 to-sky-400/20 blur-2xl opacity-40 group-hover:opacity-75 transition-opacity duration-700"
      />

      {/* 3D Animated Card Container with smooth CSS transitions */}
      <div
        className="relative rounded-3xl bg-white border border-slate-200/80 p-3 sm:p-4 shadow-xl shadow-blue-900/5 transition-transform duration-300 ease-out overflow-hidden"
        style={{
          transform: `rotateX(${transform.rotateX}deg) rotateY(${transform.rotateY}deg) scale(${transform.scale})`,
          transformStyle: 'preserve-3d',
        }}
      >
        {/* Soft Dynamic Light Glare */}
        {isHovered && (
          <div 
            className="absolute inset-0 pointer-events-none z-20 transition-opacity duration-500 rounded-3xl"
            style={{
              background: `radial-gradient(circle at ${transform.glowX}% ${transform.glowY}%, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0) 65%)`
            }}
          />
        )}

        {/* Clean Kiosk Image Frame */}
        <div className="relative rounded-2xl overflow-hidden bg-gradient-to-b from-slate-50 to-blue-50/30 p-2 border border-slate-100">
          <img
            src={kioskImage}
            alt="PrintBar Kiosk Terminal"
            className="w-full h-auto max-h-[440px] sm:max-h-[500px] object-contain mx-auto drop-shadow-md select-none"
            referrerPolicy="no-referrer"
          />
        </div>

        {/* Clean Label */}
        <div className="mt-3 text-center">
          <p className="text-xs font-semibold text-slate-700 tracking-wide">PrintBar Kiosk Terminal</p>
        </div>
      </div>
    </div>
  );
};

export const LandingView: React.FC<LandingViewProps> = ({
  onStartKioskFlow,
  onSelectHubs,
  onOpenDiagnostics,
}) => {
  const scrollToSteps = () => {
    const el = document.getElementById('how-it-works-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="space-y-20 pb-0 overflow-hidden text-slate-800">
      
      {/* 1. HERO SECTION */}
      <section className="pt-8 sm:pt-12 lg:pt-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          
          {/* Left Column: Heading, Subtitle & Action Buttons */}
          <div className="lg:col-span-7 text-left space-y-6">

            {/* Title */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold font-['Outfit'] text-slate-900 tracking-tight leading-[1.1]">
              Print Documents in <br />
              <span className="text-blue-600">Minutes</span>
            </h1>

            {/* Subtitle */}
            <p className="text-slate-600 text-base sm:text-lg max-w-xl leading-relaxed">
              Scan a QR code, upload your PDF, pay securely, and collect your print. The most frictionless way to print in modern spaces.
            </p>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 sm:gap-4 pt-2">
              <button
                onClick={() => onStartKioskFlow()}
                className="px-5 py-3 sm:px-8 sm:py-3.5 rounded-xl font-bold text-xs sm:text-sm bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-500/20 transition-all flex items-center justify-center cursor-pointer active:scale-95"
              >
                <span>Start Printing</span>
              </button>

              <button
                onClick={scrollToSteps}
                className="px-5 py-3 sm:px-7 sm:py-3.5 rounded-xl font-semibold text-xs sm:text-sm bg-slate-100 hover:bg-slate-200/80 text-slate-700 transition-all flex items-center gap-1.5 sm:gap-2 cursor-pointer"
              >
                <div className="w-4 h-4 sm:w-5 sm:h-5 rounded-full border border-slate-600 flex items-center justify-center">
                  <Play className="w-2 h-2 sm:w-2.5 sm:h-2.5 fill-slate-700 text-slate-700 ml-0.5" />
                </div>
                <span>How it Works</span>
              </button>
            </div>

          </div>

          {/* Right Column: PrintBar Kiosk Image with Interactive Cursor Animation */}
          <div className="lg:col-span-5 flex justify-center items-center">
            <InteractiveKioskImage />
          </div>

        </div>
      </section>

      {/* 2. DESIGNED FOR MODERN PRINTING */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-10">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-['Outfit']">
            Designed for Modern Printing
          </h2>
          <p className="text-slate-500 text-sm mt-2">
            The infrastructure you need to handle documents anywhere.
          </p>
        </div>

        {/* 4 Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          
          {/* Card 1 */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
              <Zap className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900 mb-1">Fast Printing</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Zero drivers, zero log. Send your documents to the printer in milliseconds.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
              <Shield className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900 mb-1">Secure Upload</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              End-to-end encryption for every file. Your privacy is our core foundation.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
              <CreditCard className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900 mb-1">Online Payment</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Seamless integration with Apple Pay, Google Pay, and Stripe.
            </p>
          </div>

          {/* Card 4 */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
              <Trash2 className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-slate-900 mb-1">Auto Deletion</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Files are automatically purged from our servers immediately after printing.
            </p>
          </div>

        </div>
      </section>

      {/* 3. READY IN 5 STEPS */}
      <section id="how-it-works-section" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-10 scroll-mt-24">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">
          
          {/* Left Column Text & Image */}
          <div className="lg:col-span-5 space-y-6">
            <div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-['Outfit']">
                Ready in 5 Steps
              </h2>
              <p className="text-slate-500 text-sm mt-3 leading-relaxed">
                We've refined the printing journey into a simple, beautiful sequence that saves you time.
              </p>
            </div>

            {/* Machine Exploded View Photo Preview */}
            <div className="rounded-2xl overflow-hidden border border-slate-200/80 shadow-md bg-white p-2">
              <img 
                src={kioskExplodedViewPhoto} 
                alt="PrintBar Kiosk - Exploded View (Inside the Smart Self-Service Printing Machine)" 
                className="w-full h-auto max-h-[420px] object-contain rounded-xl select-none"
              />
            </div>
          </div>

          {/* Right Column: 5 Steps List */}
          <div className="lg:col-span-7 space-y-6 pt-2">
            {[
              {
                num: '1',
                title: 'Scan QR',
                desc: 'Locate the PrintBar sticker on any enabled printer and point your camera. No app download required.'
              },
              {
                num: '2',
                title: 'Upload Files',
                desc: 'Select your document or image (PDF, DOC, DOCX, JPG, PNG up to 100MB). We support high-resolution previews.'
              },
              {
                num: '3',
                title: 'Choose Options',
                desc: 'Customize your print: Black & White or Color, Single or Double-sided, and select the number of copies.'
              },
              {
                num: '4',
                title: 'Pay Securely',
                desc: 'Complete your transaction with a single tap using Stripe\'s ultra-secure payment processing.'
              },
              {
                num: '5',
                title: 'Collect Print',
                desc: 'Your document is ready! Collect it from the tray and enjoy the speed of PrintBar.'
              },
            ].map((step) => (
              <div key={step.num} className="flex items-start gap-4 p-2 group">
                <div className="w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-sm mt-0.5">
                  {step.num}
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                    {step.title}
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed max-w-lg">
                    {step.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>

        </div>
      </section>

      {/* 4. BLUE CTA BANNER */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        <div className="bg-blue-600 rounded-3xl text-white p-10 sm:p-14 text-center space-y-6 shadow-xl relative overflow-hidden">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white font-['Outfit']">
            Start printing today.
          </h2>
          <p className="text-blue-100 max-w-xl mx-auto text-sm sm:text-base leading-relaxed">
            Join thousands of users who have ditched the traditional printing headache for a frictionless digital experience.
          </p>
          <div className="pt-2">
            <button
              onClick={() => onStartKioskFlow()}
              className="bg-white hover:bg-blue-50 text-blue-600 font-bold px-5 py-2.5 sm:px-8 sm:py-3.5 rounded-xl shadow-lg transition-colors cursor-pointer text-xs sm:text-sm inline-flex items-center gap-2"
            >
              <span>Start Printing Now</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* 5. FOOTER */}
      <footer className="bg-slate-900 text-slate-300 pt-12 pb-8 mt-16 text-xs border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            
            {/* Logo & Name */}
            <div className="flex items-center gap-3">
              <PrintBarLogo size="md" textColor="text-white" />
            </div>

            {/* Nav Footer Links */}
            <div className="flex flex-wrap items-center justify-center gap-6 text-slate-400 font-medium">
              <a href="#privacy" onClick={(e) => e.preventDefault()} className="hover:text-white transition-colors">Privacy Policy</a>
              <a href="#terms" onClick={(e) => e.preventDefault()} className="hover:text-white transition-colors">Terms of Service</a>
              <a href="#support" onClick={(e) => e.preventDefault()} className="hover:text-white transition-colors">Support</a>
              <button onClick={onOpenDiagnostics} className="hover:text-white transition-colors cursor-pointer">Security</button>
              <a href="#contact" onClick={(e) => e.preventDefault()} className="hover:text-white transition-colors">Contact</a>
            </div>

            {/* Social Icons */}
            <div className="flex items-center gap-4 text-slate-400">
              <a href="https://twitter.com" target="_blank" rel="noreferrer" className="hover:text-white transition-colors p-2 rounded-lg bg-slate-800/80 hover:bg-blue-600">
                <Twitter className="w-4 h-4" />
              </a>
              <a href="https://github.com" target="_blank" rel="noreferrer" className="hover:text-white transition-colors p-2 rounded-lg bg-slate-800/80 hover:bg-blue-600">
                <Github className="w-4 h-4" />
              </a>
            </div>

          </div>

          <div className="pt-6 border-t border-slate-800/80 text-center text-[11px] text-slate-500">
            © {new Date().getFullYear()} PrintBar Technologies Inc. All rights reserved. Secure Cloud Printing Kiosks.
          </div>
        </div>
      </footer>

    </div>
  );
};
