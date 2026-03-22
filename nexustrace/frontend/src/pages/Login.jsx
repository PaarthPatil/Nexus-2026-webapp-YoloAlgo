import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Box } from 'lucide-react';

export function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (!username.trim() || !password) {
      setError('Please enter both username and password.');
      return;
    }

    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b1220] flex items-center justify-center p-4 selection:bg-cyan-900/50 relative overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[500px] bg-cyan-900/10 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />
      
      <Card className="w-full max-w-sm relative z-10 border-slate-800 bg-slate-900/80 shadow-2xl backdrop-blur-xl">
        <CardHeader className="space-y-3 pb-6 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-600/10 text-cyan-400 border border-cyan-800/30">
            <Box className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl font-bold tracking-tight text-slate-100">Welcome back</CardTitle>
            <CardDescription className="text-slate-400">Sign in to your NexusTrace console</CardDescription>
          </div>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <Input 
              label="Username" 
              placeholder="admin"
              value={username}
              onChange={setUsername}
              disabled={loading}
              autoComplete="username"
            />
            <Input
              type="password"
              label="Password"
              value={password}
              onChange={setPassword}
              disabled={loading}
              autoComplete="current-password"
            />
            {error && <p className="text-sm font-medium text-red-400 bg-red-950/30 p-2 text-center rounded border border-red-900/50">{error}</p>}
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" isLoading={loading}>
              Sign In
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
