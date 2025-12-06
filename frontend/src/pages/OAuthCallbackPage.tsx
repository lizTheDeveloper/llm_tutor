import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';
import { authService } from '../services/authService';
import { useAppDispatch } from '../hooks/useRedux';
import { setUser } from '../store/slices/authSlice';

function OAuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleOAuthCallback = async () => {
      try {
        // Check for error from OAuth provider
        const errorParam = searchParams.get('error');
        if (errorParam) {
          setError('OAuth authentication failed. Please try again.');
          setTimeout(() => navigate('/login'), 3000);
          return;
        }

        // Get the temporary code and provider
        const code = searchParams.get('code');
        const provider = searchParams.get('provider') as 'github' | 'google';

        if (!code || !provider) {
          setError('Missing OAuth parameters. Please try logging in again.');
          setTimeout(() => navigate('/login'), 3000);
          return;
        }

        // Exchange code for session (backend sets httpOnly cookies)
        const authResponse = await authService.exchangeOAuthCode(code, provider);

        // Backend sets httpOnly cookies automatically
        // No manual token storage needed

        // Update Redux store with user data only
        dispatch(
          setUser({
            id: authResponse.user.id,
            email: authResponse.user.email,
            name: authResponse.user.name,
            role: authResponse.user.role,
            emailVerified: authResponse.user.email_verified,
          })
        );

        // Redirect to dashboard
        navigate('/dashboard', { replace: true });
      } catch (err: any) {
        console.error('OAuth callback error:', err);
        const errorMessage =
          err.response?.data?.error?.message ||
          'Authentication failed. Please try again.';
        setError(errorMessage);
        setTimeout(() => navigate('/login'), 3000);
      }
    };

    handleOAuthCallback();
  }, [searchParams, navigate, dispatch]);

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        p: 3,
      }}
    >
      {error ? (
        <Alert severity="error" sx={{ maxWidth: 500 }}>
          {error}
          <br />
          <Typography variant="caption">Redirecting to login...</Typography>
        </Alert>
      ) : (
        <Box sx={{ textAlign: 'center' }}>
          <CircularProgress size={60} sx={{ mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Completing authentication...
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Please wait while we finish logging you in.
          </Typography>
        </Box>
      )}
    </Box>
  );
}

export default OAuthCallbackPage;
