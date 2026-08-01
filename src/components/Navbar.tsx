import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { PrintBarLogo } from './PrintBarLogo';
import { 
  Printer, 
  LayoutDashboard, 
  Lock,
  X,
  UserCheck,
  LogOut,
  ShieldAlert
} from 'lucide-react';

interface NavbarProps {
  onlineHubsCount: number;
  totalHubsCount: number;
  onStartKioskFlow: () => void;
  isAdminLoggedIn: boolean;
  onAdminLogin: (user: string, pass: string) => Promise<boolean>;
  onAdminLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  onStartKioskFlow,
  isAdminLoggedIn,
  onAdminLogin,
  onAdminLogout,
}) => {
  const navigate = useNavigate();
  const location = useLocation();

  const [isSignInModalOpen, setIsSignInModalOpen] = useState(false);
  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [loginError, setLoginError] = useState(false);

  const getActiveView = () => {
    const path = location.pathname;
    if (path === '/kiosk') return 'kiosk';
    if (path === '/locations') return 'locations';
    if (path === '/status') return 'status';
    if (path === '/admin') return 'admin';
    return 'landing';
  };

  const currentView = getActiveView();

  const handleSignInSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(false);
    const success = await onAdminLogin(usernameInput, passwordInput);
    if (success) {
      setIsSignInModalOpen(false);
      setUsernameInput('');
      setPasswordInput('');
      navigate('/admin');
    } else {
      setLoginError(true);
    }
  };

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between bg-white">
          
          {/* Brand Logo */}
          <Link 
            to="/" 
            className="flex items-center group hover:opacity-90 transition-opacity"
          >
            <PrintBarLogo size="md" showText={true} />
          </Link>

          {/* Navigation Tabs */}
          <nav className="hidden lg:flex items-center gap-8">
            <Link
              to="/"
              className={`text-sm transition-all relative py-1 ${
                currentView === 'landing'
                  ? 'text-blue-600 font-semibold border-b-2 border-blue-600'
                  : 'text-slate-600 hover:text-slate-900 font-medium'
              }`}
            >
              Product
            </Link>

            <Link
              to="/status"
              className={`text-sm transition-all relative py-1 ${
                currentView === 'status'
                  ? 'text-blue-600 font-semibold border-b-2 border-blue-600'
                  : 'text-slate-600 hover:text-slate-900 font-medium'
              }`}
            >
              Security
            </Link>

            {/* Admin Portal Tab - Shown BESIDE Security ONLY IF Logged In */}
            {isAdminLoggedIn && (
              <Link
                to="/admin"
                className={`text-sm transition-all relative py-1 flex items-center gap-1.5 ${
                  currentView === 'admin'
                    ? 'text-blue-600 font-semibold border-b-2 border-blue-600'
                    : 'text-slate-600 hover:text-slate-900 font-medium'
                }`}
              >
                <LayoutDashboard className="w-4 h-4 text-blue-600" />
                <span>Admin Portal</span>
              </Link>
            )}
          </nav>

          {/* Right Nav Action Controls */}
          <div className="flex items-center gap-3">
            
            {isAdminLoggedIn ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate('/admin')}
                  className="hidden sm:flex items-center gap-2 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold px-3 py-2 rounded-xl transition-colors cursor-pointer border border-blue-200"
                >
                  <UserCheck className="w-3.5 h-3.5 text-blue-600" />
                  <span>Juned (Admin)</span>
                </button>

                <button
                  onClick={onAdminLogout}
                  title="Sign Out"
                  className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-xl transition-colors cursor-pointer"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setLoginError(false);
                  setIsSignInModalOpen(true);
                }}
                className="text-slate-600 hover:text-slate-900 text-sm font-semibold px-3 py-2 cursor-pointer transition-colors"
              >
                Sign In
              </button>
            )}

          </div>

        </div>
      </header>

      {/* SIGN IN MODAL DIALOG */}
      {isSignInModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl relative space-y-6">
            
            {/* Close Button */}
            <button
              onClick={() => setIsSignInModalOpen(false)}
              className="absolute top-5 right-5 text-slate-400 hover:text-slate-700 p-1 rounded-full transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Header Logo & Title */}
            <div className="text-center space-y-3">
              <div className="flex justify-center">
                <PrintBarLogo size="lg" showText={false} />
              </div>
              <h2 className="text-xl font-bold font-['Outfit'] text-slate-900">
                Admin Sign In
              </h2>
              <p className="text-xs text-slate-500 leading-relaxed font-normal">
                Enter your credentials to unlock the PrintBar Admin Command Center.
              </p>
            </div>

            {/* Error banner */}
            {loginError && (
              <div className="bg-red-50 border border-red-200/80 rounded-xl p-3 text-xs text-red-700 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-600 shrink-0" />
                <span>Invalid username or password. Please try again.</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSignInSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  User Name
                </label>
                <input
                  type="text"
                  required
                  value={usernameInput}
                  onChange={(e) => setUsernameInput(e.target.value)}
                  placeholder="Enter User Name"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  required
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  placeholder="Enter Password"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-blue-500 focus:bg-white"
                />
              </div>

              <button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm py-3 rounded-xl transition-colors cursor-pointer shadow-xs active:scale-95"
              >
                Sign In
              </button>
            </form>

          </div>
        </div>
      )}
    </>
  );
};
