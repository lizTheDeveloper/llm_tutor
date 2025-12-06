import React, { useEffect } from 'react';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
  Chip,
  LinearProgress,
  Paper,
  Divider,
} from '@mui/material';
import {
  EmojiEvents,
  Whatshot,
  TrendingUp,
  Lock,
  CheckCircle,
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../hooks/useRedux';
import {
  fetchProgressMetrics,
  fetchAchievements,
  fetchBadges,
} from '../store/slices/progressSlice';

const ProgressDashboardPage: React.FC = () => {
  const dispatch = useAppDispatch();

  const {
    metrics,
    achievements,
    badges,
    loading,
    error,
  } = useAppSelector((state) => state.progress);

  useEffect(() => {
    dispatch(fetchProgressMetrics());
    dispatch(fetchAchievements());
    dispatch(fetchBadges());
  }, [dispatch]);

  if (loading) {
    return (
      <Box
        data-testid="progress-dashboard-page"
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="80vh"
      >
        <CircularProgress />
        <Typography variant="body1" sx={{ ml: 2 }}>
          Loading your progress...
        </Typography>
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" data-testid="progress-dashboard-page" sx={{ py: 4 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Typography variant="h4" gutterBottom>
        Your Progress
      </Typography>

      {/* Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={2}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <CheckCircle color="success" sx={{ mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Exercises Completed
                </Typography>
              </Box>
              <Typography variant="h3" color="primary">
                {metrics?.exercises_completed || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={2}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Whatshot color="error" sx={{ mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Current Streak
                </Typography>
              </Box>
              <Typography variant="h3" color="primary">
                {metrics?.current_streak || 0}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Longest: {metrics?.longest_streak || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={2}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <TrendingUp color="success" sx={{ mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Average Grade
                </Typography>
              </Box>
              <Typography variant="h3" color="primary">
                {metrics?.average_grade?.toFixed(1) || '0.0'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={2}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <EmojiEvents color="warning" sx={{ mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Achievements
                </Typography>
              </Box>
              <Typography variant="h3" color="primary">
                {achievements?.filter((a) => a.unlocked).length || 0}
                <Typography variant="caption" component="span" sx={{ ml: 1 }}>
                  / {achievements?.length || 0}
                </Typography>
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Achievements Section */}
      <Card elevation={3} sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h5" gutterBottom>
            Achievements
          </Typography>
          <Divider sx={{ mb: 2 }} />

          {achievements && achievements.length > 0 ? (
            <Grid container spacing={2}>
              {achievements.map((achievement) => (
                <Grid item xs={12} sm={6} md={4} key={achievement.id}>
                  <Paper
                    elevation={achievement.unlocked ? 2 : 0}
                    sx={{
                      p: 2,
                      opacity: achievement.unlocked ? 1 : 0.6,
                      borderWidth: 1,
                      borderStyle: 'solid',
                      borderColor: achievement.unlocked ? 'primary.main' : 'grey.300',
                    }}
                  >
                    <Box display="flex" alignItems="center" mb={1}>
                      {achievement.unlocked ? (
                        <EmojiEvents color="warning" sx={{ mr: 1 }} />
                      ) : (
                        <Lock color="disabled" sx={{ mr: 1 }} />
                      )}
                      <Typography variant="h6" noWrap>
                        {achievement.title}
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" paragraph>
                      {achievement.description}
                    </Typography>
                    {!achievement.unlocked && (
                      <>
                        <LinearProgress
                          variant="determinate"
                          value={achievement.progress_percentage || 0}
                          sx={{ mb: 1 }}
                        />
                        <Typography variant="caption" color="text.secondary">
                          {achievement.current_value} / {achievement.criteria_value}
                        </Typography>
                      </>
                    )}
                    {achievement.unlocked && achievement.unlocked_at && (
                      <Chip
                        label={`Unlocked ${new Date(achievement.unlocked_at).toLocaleDateString()}`}
                        size="small"
                        color="success"
                      />
                    )}
                  </Paper>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Typography variant="body2" color="text.secondary" textAlign="center">
              No achievements yet. Keep exercising to unlock achievements!
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Badges Section */}
      {badges && badges.length > 0 && (
        <Card elevation={3}>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              Badges
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Grid container spacing={2}>
              {badges.map((badge) => (
                <Grid item key={badge.id}>
                  <Chip
                    label={badge.name}
                    color={badge.earned ? 'primary' : 'default'}
                    icon={badge.earned ? <CheckCircle /> : <Lock />}
                    sx={{ opacity: badge.earned ? 1 : 0.6 }}
                  />
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}
    </Container>
  );
};

export default ProgressDashboardPage;
