import React, { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../hooks/useRedux';
import {
  fetchUserProfile,
  updateUserProfile,
  type ProfileUpdateData,
  type UserProfile,
} from '../store/slices/profileSlice';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  Grid,
  Avatar,
  Divider,
  TextField,
  MenuItem,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  Chip,
} from '@mui/material';
import {
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';

const PROGRAMMING_LANGUAGES = [
  'python',
  'javascript',
  'typescript',
  'java',
  'c++',
  'c#',
  'go',
  'rust',
  'ruby',
  'php',
  'swift',
  'kotlin',
];

const SKILL_LEVELS = ['beginner', 'intermediate', 'advanced'];

const LEARNING_STYLES = ['hands-on', 'visual', 'reading', 'video'];

const TIME_COMMITMENTS = [
  '15-30 minutes',
  '30-60 minutes',
  '1-2 hours',
  '2+ hours',
];

const ProfilePage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { currentProfile, loading, error } = useAppSelector(
    (state) => state.profile
  );

  const [isEditing, setIsEditing] = useState(false);
  const [editedProfile, setEditedProfile] = useState<Partial<ProfileUpdateData>>({});
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    dispatch(fetchUserProfile());
  }, [dispatch]);

  const handleEditClick = () => {
    if (currentProfile) {
      setEditedProfile({
        name: currentProfile.name,
        bio: currentProfile.bio || '',
        programming_language: currentProfile.programming_language || '',
        skill_level: currentProfile.skill_level || undefined,
        career_goals: currentProfile.career_goals || '',
        learning_style: currentProfile.learning_style || '',
        time_commitment: currentProfile.time_commitment || '',
      });
    }
    setIsEditing(true);
    setSuccessMessage(null);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedProfile({});
    setValidationErrors({});
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!editedProfile.name?.trim()) {
      errors.name = 'Name is required';
    }

    if (editedProfile.career_goals && editedProfile.career_goals.trim().length < 10) {
      errors.career_goals = 'Career goals must be at least 10 characters';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    setSaving(true);
    setSuccessMessage(null);

    try {
      // Filter out empty optional fields
      const updateData: ProfileUpdateData = {};

      if (editedProfile.name) updateData.name = editedProfile.name;
      if (editedProfile.bio !== undefined) updateData.bio = editedProfile.bio;
      if (editedProfile.programming_language) updateData.programming_language = editedProfile.programming_language;
      if (editedProfile.skill_level) updateData.skill_level = editedProfile.skill_level;
      if (editedProfile.career_goals) updateData.career_goals = editedProfile.career_goals;
      if (editedProfile.learning_style) updateData.learning_style = editedProfile.learning_style;
      if (editedProfile.time_commitment) updateData.time_commitment = editedProfile.time_commitment;

      await dispatch(updateUserProfile(updateData)).unwrap();

      setSuccessMessage('Profile updated successfully');
      setIsEditing(false);
      setSaving(false);
    } catch (updateError: any) {
      setSaving(false);
      // Error will be in Redux state
    }
  };

  const handleFieldChange = (field: keyof ProfileUpdateData, value: any) => {
    setEditedProfile((prev) => ({ ...prev, [field]: value }));
    // Clear validation error for this field
    if (validationErrors[field]) {
      setValidationErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const handleRetry = () => {
    dispatch(fetchUserProfile());
  };

  if (loading && !currentProfile) {
    return (
      <Container maxWidth="md" sx={{ mt: 8, textAlign: 'center' }}>
        <CircularProgress />
        <Typography variant="body1" sx={{ mt: 2 }}>
          Loading profile...
        </Typography>
      </Container>
    );
  }

  if (error && !currentProfile) {
    return (
      <Container maxWidth="md" sx={{ mt: 8 }}>
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={handleRetry}>
              Retry
            </Button>
          }
        >
          Failed to load profile. {error}
        </Alert>
      </Container>
    );
  }

  if (!currentProfile) {
    return (
      <Container maxWidth="md" sx={{ mt: 8 }}>
        <Alert severity="info">No profile data available.</Alert>
      </Container>
    );
  }

  const getAvatarLetter = (name: string) => {
    return name.charAt(0).toUpperCase();
  };

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'MMMM d, yyyy');
    } catch {
      return dateString;
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Success Message */}
      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Error Message */}
      {error && !saving && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Profile Header */}
      <Paper elevation={3} sx={{ p: 4, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
          <Avatar
            src={currentProfile.avatar_url || undefined}
            sx={{ width: 100, height: 100, mr: 3, fontSize: '2.5rem' }}
            data-testid="user-avatar"
          >
            {getAvatarLetter(currentProfile.name)}
          </Avatar>

          <Box sx={{ flex: 1 }}>
            {isEditing ? (
              <TextField
                label="Name"
                value={editedProfile.name || ''}
                onChange={(e) => handleFieldChange('name', e.target.value)}
                error={!!validationErrors.name}
                helperText={validationErrors.name}
                fullWidth
                sx={{ mb: 2 }}
              />
            ) : (
              <>
                <Typography variant="h4" component="h1" gutterBottom>
                  {currentProfile.name}
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  {currentProfile.email}
                </Typography>
                <Box sx={{ mt: 1 }}>
                  <Chip
                    label={currentProfile.role}
                    size="small"
                    color="primary"
                    sx={{ mr: 1 }}
                  />
                  {currentProfile.is_mentor && (
                    <Chip label="Mentor" size="small" color="secondary" />
                  )}
                </Box>
              </>
            )}
          </Box>

          <Box>
            {!isEditing ? (
              <Button
                variant="contained"
                startIcon={<EditIcon />}
                onClick={handleEditClick}
              >
                Edit Profile
              </Button>
            ) : (
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? 'Saving...' : 'Save'}
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<CancelIcon />}
                  onClick={handleCancelEdit}
                  disabled={saving}
                >
                  Cancel
                </Button>
              </Box>
            )}
          </Box>
        </Box>

        <Divider sx={{ my: 3 }} />

        {/* Bio Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            About
          </Typography>
          {isEditing ? (
            <TextField
              label="Bio"
              value={editedProfile.bio || ''}
              onChange={(e) => handleFieldChange('bio', e.target.value)}
              multiline
              rows={3}
              fullWidth
              placeholder="Tell us about yourself..."
            />
          ) : (
            <Typography variant="body1" color="text.secondary">
              {currentProfile.bio || 'No bio provided'}
            </Typography>
          )}
        </Box>
      </Paper>

      <Grid container spacing={3}>
        {/* Learning Preferences */}
        <Grid item xs={12} md={6}>
          <Paper elevation={3} sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Learning Preferences
            </Typography>
            <Divider sx={{ mb: 2 }} />

            {isEditing ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  select
                  label="Programming Language"
                  value={editedProfile.programming_language || ''}
                  onChange={(e) => handleFieldChange('programming_language', e.target.value)}
                  fullWidth
                >
                  {PROGRAMMING_LANGUAGES.map((lang) => (
                    <MenuItem key={lang} value={lang}>
                      {lang.charAt(0).toUpperCase() + lang.slice(1)}
                    </MenuItem>
                  ))}
                </TextField>

                <TextField
                  select
                  label="Skill Level"
                  value={editedProfile.skill_level || ''}
                  onChange={(e) => handleFieldChange('skill_level', e.target.value)}
                  fullWidth
                >
                  {SKILL_LEVELS.map((level) => (
                    <MenuItem key={level} value={level}>
                      {level.charAt(0).toUpperCase() + level.slice(1)}
                    </MenuItem>
                  ))}
                </TextField>

                <TextField
                  label="Career Goals"
                  value={editedProfile.career_goals || ''}
                  onChange={(e) => handleFieldChange('career_goals', e.target.value)}
                  error={!!validationErrors.career_goals}
                  helperText={validationErrors.career_goals || 'Minimum 10 characters'}
                  multiline
                  rows={3}
                  fullWidth
                />

                <TextField
                  select
                  label="Learning Style"
                  value={editedProfile.learning_style || ''}
                  onChange={(e) => handleFieldChange('learning_style', e.target.value)}
                  fullWidth
                >
                  {LEARNING_STYLES.map((style) => (
                    <MenuItem key={style} value={style}>
                      {style.charAt(0).toUpperCase() + style.slice(1)}
                    </MenuItem>
                  ))}
                </TextField>

                <TextField
                  select
                  label="Time Commitment"
                  value={editedProfile.time_commitment || ''}
                  onChange={(e) => handleFieldChange('time_commitment', e.target.value)}
                  fullWidth
                >
                  {TIME_COMMITMENTS.map((time) => (
                    <MenuItem key={time} value={time}>
                      {time}
                    </MenuItem>
                  ))}
                </TextField>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <ProfileItem
                  label="Programming Language"
                  value={currentProfile.programming_language}
                />
                <ProfileItem label="Skill Level" value={currentProfile.skill_level} />
                <ProfileItem label="Career Goals" value={currentProfile.career_goals} />
                <ProfileItem label="Learning Style" value={currentProfile.learning_style} />
                <ProfileItem label="Time Commitment" value={currentProfile.time_commitment} />
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Progress Statistics */}
        <Grid item xs={12} md={6}>
          <Paper elevation={3} sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Progress Statistics
            </Typography>
            <Divider sx={{ mb: 2 }} />

            <Grid container spacing={2}>
              <Grid item xs={6}>
                <StatCard
                  label="Current Streak"
                  value={currentProfile.current_streak}
                  unit="days"
                />
              </Grid>
              <Grid item xs={6}>
                <StatCard
                  label="Longest Streak"
                  value={currentProfile.longest_streak}
                  unit="days"
                />
              </Grid>
              <Grid item xs={12}>
                <StatCard
                  label="Exercises Completed"
                  value={currentProfile.exercises_completed}
                  unit="total"
                />
              </Grid>
            </Grid>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Typography variant="body2" color="text.secondary">
                <strong>Member Since:</strong>{' '}
                {formatDate(currentProfile.created_at)}
              </Typography>
              {currentProfile.last_login && (
                <Typography variant="body2" color="text.secondary">
                  <strong>Last Active:</strong>{' '}
                  {formatDate(currentProfile.last_login)}
                </Typography>
              )}
              {currentProfile.last_exercise_date && (
                <Typography variant="body2" color="text.secondary">
                  <strong>Last Exercise:</strong>{' '}
                  {formatDate(currentProfile.last_exercise_date)}
                </Typography>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Personal Information */}
        <Grid item xs={12}>
          <Paper elevation={3} sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Personal Information
            </Typography>
            <Divider sx={{ mb: 2 }} />

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Email:</strong> {currentProfile.email}
                </Typography>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Account Status:</strong>{' '}
                  {currentProfile.is_active ? 'Active' : 'Inactive'}
                </Typography>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Onboarding:</strong>{' '}
                  {currentProfile.onboarding_completed ? 'Completed' : 'Pending'}
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

// Helper Components
interface ProfileItemProps {
  label: string;
  value: string | null | undefined;
}

const ProfileItem: React.FC<ProfileItemProps> = ({ label, value }) => (
  <Box>
    <Typography variant="body2" color="text.secondary" gutterBottom>
      {label}
    </Typography>
    <Typography variant="body1">
      {value ? value.charAt(0).toUpperCase() + value.slice(1) : 'Not set'}
    </Typography>
  </Box>
);

interface StatCardProps {
  label: string;
  value: number;
  unit: string;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, unit }) => (
  <Card variant="outlined">
    <CardContent sx={{ textAlign: 'center' }}>
      <Typography variant="h4" component="div" color="primary">
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {unit}
      </Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        {label}
      </Typography>
    </CardContent>
  </Card>
);

export default ProfilePage;
