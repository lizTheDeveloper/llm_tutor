import React, { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Divider,
  Paper,
} from '@mui/material';
import {
  PlayArrow,
  Add,
  Refresh,
  CheckCircle,
  SkipNext,
  Schedule,
  EmojiEvents,
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../hooks/useRedux';
import {
  fetchDailyExercise,
  fetchExerciseHistory,
} from '../store/slices/exerciseSlice';

const ExerciseDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const {
    dailyExercise,
    exerciseHistory,
    loading,
    error,
  } = useAppSelector((state) => state.exercise);

  useEffect(() => {
    dispatch(fetchDailyExercise());
    dispatch(fetchExerciseHistory({ limit: 10 }));
  }, [dispatch]);

  const stats = useMemo(() => {
    const historyList = exerciseHistory || [];
    const completed = historyList.filter((ex) => ex.status === 'completed');
    const totalCompleted = completed.length;
    const averageGrade = completed.length > 0
      ? completed.reduce((sum, ex) => sum + (ex.grade || 0), 0) / completed.length
      : 0;

    return {
      totalCompleted,
      averageGrade,
    };
  }, [exerciseHistory]);

  const handleStartExercise = () => {
    if (dailyExercise?.exercise.id) {
      navigate(`/exercises/${dailyExercise.exercise.id}`);
    }
  };

  const handleGenerateExercise = () => {
    // Navigate to exercise generation page or open modal
    navigate('/exercises/generate');
  };

  const handleRetry = () => {
    dispatch(fetchDailyExercise());
    dispatch(fetchExerciseHistory({ limit: 10 }));
  };

  const handleHistoryItemClick = (exerciseId: number) => {
    navigate(`/exercises/${exerciseId}`);
  };

  const getDifficultyColor = (difficulty: string): 'success' | 'warning' | 'error' => {
    switch (difficulty) {
      case 'EASY':
        return 'success';
      case 'MEDIUM':
        return 'warning';
      case 'HARD':
        return 'error';
      default:
        return 'warning';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="success" fontSize="small" />;
      case 'skipped':
        return <SkipNext color="disabled" fontSize="small" />;
      default:
        return <Schedule color="action" fontSize="small" />;
    }
  };

  if (loading) {
    return (
      <Box
        data-testid="exercise-dashboard-page"
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="80vh"
      >
        <CircularProgress />
        <Typography variant="body1" sx={{ ml: 2 }}>
          Loading your daily exercise...
        </Typography>
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" data-testid="exercise-dashboard-page" sx={{ py: 4 }}>
      {error && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={handleRetry}>
              Retry
            </Button>
          }
          sx={{ mb: 3 }}
        >
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Quick Stats Section */}
        <Grid item xs={12}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Paper elevation={2} sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h4" color="primary">
                  {stats.totalCompleted}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Exercises Completed
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Paper elevation={2} sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h4" color="primary">
                  {stats.averageGrade.toFixed(1)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Average Grade
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        </Grid>

        {/* Daily Exercise Section */}
        <Grid item xs={12} md={8}>
          <Card elevation={3}>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                Today's Challenge
              </Typography>
              <Divider sx={{ mb: 2 }} />

              {dailyExercise ? (
                <>
                  <Box display="flex" alignItems="center" gap={1} mb={2}>
                    <Typography variant="h6">
                      {dailyExercise.exercise.title}
                    </Typography>
                    <Chip
                      label={dailyExercise.exercise.difficulty}
                      color={getDifficultyColor(dailyExercise.exercise.difficulty)}
                      size="small"
                    />
                  </Box>

                  <Typography variant="body2" color="text.secondary" paragraph>
                    {dailyExercise.exercise.description}
                  </Typography>

                  <Box display="flex" alignItems="center" gap={2} mb={2}>
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <Schedule fontSize="small" color="action" />
                      <Typography variant="body2" color="text.secondary">
                        {dailyExercise.exercise.estimated_time_minutes} minutes
                      </Typography>
                    </Box>
                    <Chip
                      label={dailyExercise.exercise.language}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={dailyExercise.exercise.exercise_type}
                      size="small"
                      variant="outlined"
                    />
                  </Box>

                  {dailyExercise.exercise.learning_objectives.length > 0 && (
                    <Box mb={2}>
                      <Typography variant="subtitle2" gutterBottom>
                        Learning Objectives:
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        {dailyExercise.exercise.learning_objectives.map((obj, index) => (
                          <Chip key={index} label={obj} size="small" />
                        ))}
                      </Box>
                    </Box>
                  )}

                  <Button
                    variant="contained"
                    startIcon={<PlayArrow />}
                    onClick={handleStartExercise}
                    size="large"
                    fullWidth
                  >
                    Start Exercise
                  </Button>
                </>
              ) : (
                <Box textAlign="center" py={4}>
                  <Typography variant="body1" color="text.secondary" paragraph>
                    No daily exercise available yet.
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<Add />}
                    onClick={handleGenerateExercise}
                  >
                    Generate Exercise
                  </Button>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Exercise History Sidebar */}
        <Grid item xs={12} md={4}>
          <Card elevation={3}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Exercises
              </Typography>
              <Divider sx={{ mb: 2 }} />

              {exerciseHistory && exerciseHistory.length > 0 ? (
                <List dense>
                  {exerciseHistory.map((exercise) => (
                    <React.Fragment key={exercise.id}>
                      <ListItem disablePadding>
                        <ListItemButton onClick={() => handleHistoryItemClick(exercise.id)}>
                          <ListItemText
                            primary={
                              <Box display="flex" alignItems="center" gap={1}>
                                {getStatusIcon(exercise.status)}
                                <Typography variant="body2" noWrap>
                                  {exercise.title}
                                </Typography>
                              </Box>
                            }
                            secondary={
                              <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                                <Chip
                                  label={exercise.difficulty}
                                  size="small"
                                  color={getDifficultyColor(exercise.difficulty)}
                                  sx={{ height: 20, fontSize: '0.7rem' }}
                                />
                                {exercise.status === 'completed' && exercise.grade !== null && (
                                  <Chip
                                    label={exercise.grade}
                                    size="small"
                                    icon={<EmojiEvents />}
                                    sx={{ height: 20, fontSize: '0.7rem' }}
                                  />
                                )}
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                  sx={{ textTransform: 'capitalize' }}
                                >
                                  {exercise.status}
                                </Typography>
                              </Box>
                            }
                          />
                        </ListItemButton>
                      </ListItem>
                      <Divider />
                    </React.Fragment>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  No exercise history yet. Start your first exercise!
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
};

export default ExerciseDashboardPage;
