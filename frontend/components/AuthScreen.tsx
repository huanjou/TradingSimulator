import React, { useState, useEffect } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { TrendingUp } from 'lucide-react';

export default function AuthScreen() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login, register, error, clearError } = useAuthStore();

  useEffect(() => {
    clearError();
  }, [isLogin, clearError]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (isLogin) {
        await login({ email, password, remember_me: rememberMe });
      } else {
        await register({ email, password, remember_me: rememberMe });
      }
    } catch (err: any) {
      // Error is handled in the store, but we catch it to prevent unhandled promise rejections
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center p-4">
      <div className="flex flex-col items-center gap-2 mb-8">
        <TrendingUp className="w-12 h-12 text-emerald-500 mb-4" />
        <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">Scalpy</h1>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl text-zinc-100 font-semibold mb-6">
          {isLogin ? 'Sign In' : 'Create Account'}
        </h2>

        {error && (
          <div className="bg-rose-500/10 border border-rose-500/50 text-rose-500 text-sm p-3 rounded mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm text-zinc-400">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded p-3 text-zinc-100 outline-none focus:border-emerald-500 transition-colors"
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm text-zinc-400">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded p-3 text-zinc-100 outline-none focus:border-emerald-500 transition-colors"
              placeholder="••••••••"
              required
            />
          </div>

          <div className="flex items-center gap-2 mt-1 mb-2">
            <input
              type="checkbox"
              id="rememberMe"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 text-emerald-500 bg-zinc-800 border-zinc-700 rounded focus:ring-emerald-500 focus:ring-offset-zinc-900"
            />
            <label
              htmlFor="rememberMe"
              className="text-sm text-zinc-400 cursor-pointer select-none"
            >
              Remember me
            </label>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded mt-2 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Processing...' : isLogin ? 'Sign In' : 'Sign Up'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-zinc-500">
          {isLogin ? "Don't have an account? " : 'Already have an account? '}
          <button onClick={() => setIsLogin(!isLogin)} className="text-emerald-500 hover:underline">
            {isLogin ? 'Sign Up' : 'Sign In'}
          </button>
        </div>
      </div>
    </div>
  );
}
