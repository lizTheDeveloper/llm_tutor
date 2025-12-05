import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../hooks/useRedux';
import {
  fetchOnboardingStatus,
  submitOnboarding,
  type OnboardingData,
} from '../store/slices/profileSlice';
import {
  Box,
  Container,
  Paper,
  Typography,
  Stepper,
  Step,
  StepLabel,
  Button,
  LinearProgress,
  Alert,
  CircularProgress,
} from '@mui/material';
import apiClient from '../services/api';

interface Question {
  id: string;
  question: string;
  type: 'select' | 'textarea' | 'text';
  options?: string[];
  required?: boolean;
  minLength?: number;
  maxLength?: number;
}

interface OnboardingQuestions {
  questions: Question[];
  total_questions: number;
  estimated_time: string;
}

interface OnboardingProgress {
  currentStep: number;
  answers: Record<string, string>;
}

const OnboardingPage: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { onboardingStatus, loading: profileLoading, error: profileError } = useAppSelector(
    (state) => state.profile
  );

  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load questions and check onboarding status on mount
  useEffect(() => {
    const initializeOnboarding = async () => {
      try {
        // Check if onboarding already completed
        const statusResult = await dispatch(fetchOnboardingStatus()).unwrap();
        if (statusResult.onboarding_completed) {
          navigate('/dashboard');
          return;
        }

        // Fetch onboarding questions
        const response = await apiClient.get('/v1/users/onboarding/questions');
        setQuestions(response.data.questions);

        // Try to resume from saved progress
        const savedProgress = localStorage.getItem('onboarding_progress');
        if (savedProgress) {
          try {
            const progress: OnboardingProgress = JSON.parse(savedProgress);
            setCurrentStep(progress.currentStep);
            setAnswers(progress.answers);
          } catch (parseError) {
            console.error('Failed to parse saved progress:', parseError);
            localStorage.removeItem('onboarding_progress');
          }
        }

        setLoading(false);
      } catch (fetchError: any) {
        setError(fetchError.message || 'Failed to load onboarding questions');
        setLoading(false);
      }
    };

    initializeOnboarding();
  }, [dispatch, navigate]);

  // Save progress to localStorage whenever answers or step changes
  useEffect(() => {
    if (questions.length > 0 && !loading) {
      const progress: OnboardingProgress = {
        currentStep,
        answers,
      };
      localStorage.setItem('onboarding_progress', JSON.stringify(progress));
    }
  }, [currentStep, answers, questions.length, loading]);

  const validateField = (question: Question, value: string): string | null => {
    if (question.required && !value.trim()) {
      return 'This field is required';
    }

    if (question.minLength && value.trim().length < question.minLength) {
      return `Must be at least ${question.minLength} characters`;
    }

    if (question.maxLength && value.trim().length > question.maxLength) {
      return `Must be no more than ${question.maxLength} characters`;
    }

    return null;
  };

  const handleNext = () => {
    const currentQuestion = questions[currentStep];
    const currentValue = answers[currentQuestion.id] || '';

    // Validate current field
    const validationError = validateField(currentQuestion, currentValue);
    if (validationError) {
      setFieldErrors({ [currentQuestion.id]: validationError });
      return;
    }

    setFieldErrors({});
    setCurrentStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setFieldErrors({});
    setCurrentStep((prev) => prev - 1);
  };

  const handleSubmit = async () => {
    const currentQuestion = questions[currentStep];
    const currentValue = answers[currentQuestion.id] || '';

    // Validate current field
    const validationError = validateField(currentQuestion, currentValue);
    if (validationError) {
      setFieldErrors({ [currentQuestion.id]: validationError });
      return;
    }

    setFieldErrors({});
    setSubmitting(true);
    setError(null);

    try {
      // Map answers to onboarding data structure
      const onboardingData: OnboardingData = {
        programming_language: answers.programming_language,
        skill_level: answers.skill_level as OnboardingData['skill_level'],
        career_goals: answers.career_goals,
        learning_style: answers.learning_style,
        time_commitment: answers.time_commitment,
      };

      // Submit onboarding
      await dispatch(submitOnboarding(onboardingData)).unwrap();

      // Clear saved progress
      localStorage.removeItem('onboarding_progress');

      // Show success message
      setSuccessMessage('Onboarding completed successfully!');

      // Redirect to dashboard after a brief delay
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } catch (submitError: any) {
      setError(submitError.message || submitError);
      setSubmitting(false);
    }
  };

  const handleFieldChange = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    // Clear field error when user types
    if (fieldErrors[questionId]) {
      setFieldErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[questionId];
        return newErrors;
      });
    }
  };

  const handleRetry = () => {
    setError(null);
    setLoading(true);
    window.location.reload();
  };

  if (loading) {
    return (
      <Container maxWidth="md" sx={{ mt: 8, textAlign: 'center' }}>
        <CircularProgress />
        <Typography variant="body1" sx={{ mt: 2 }}>
          Loading onboarding questions...
        </Typography>
      </Container>
    );
  }

  if (error) {
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
          {error}
        </Alert>
      </Container>
    );
  }

  if (questions.length === 0) {
    return (
      <Container maxWidth="md" sx={{ mt: 8 }}>
        <Alert severity="info">No onboarding questions available.</Alert>
      </Container>
    );
  }

  const currentQuestion = questions[currentStep];
  const progress = ((currentStep + 1) / questions.length) * 100;
  const isLastStep = currentStep === questions.length - 1;

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            Welcome! Let's Get Started
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Tell us about yourself so we can personalize your learning experience.
          </Typography>
        </Box>

        {/* Progress Indicator */}
        <Box sx={{ mb: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Step {currentStep + 1} of {questions.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {Math.round(progress)}% Complete
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={progress}
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            role="progressbar"
          />
        </Box>

        {/* Stepper */}
        <Stepper activeStep={currentStep} sx={{ mb: 4 }} alternativeLabel>
          {questions.map((q, index) => (
            <Step key={q.id}>
              <StepLabel />
            </Step>
          ))}
        </Stepper>

        {/* Success Message */}
        {successMessage && (
          <Alert severity="success" sx={{ mb: 3 }}>
            {successMessage}
          </Alert>
        )}

        {/* Error Message */}
        {error && !submitting && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Current Question */}
        <Box sx={{ mb: 4 }}>
          <QuestionField
            question={currentQuestion}
            value={answers[currentQuestion.id] || ''}
            onChange={(value) => handleFieldChange(currentQuestion.id, value)}
            error={fieldErrors[currentQuestion.id]}
          />
        </Box>

        {/* Navigation Buttons */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button
            onClick={handleBack}
            disabled={currentStep === 0}
            variant="outlined"
          >
            Back
          </Button>

          {isLastStep ? (
            <Button
              onClick={handleSubmit}
              disabled={submitting}
              variant="contained"
              color="primary"
            >
              {submitting ? 'Submitting...' : 'Submit'}
            </Button>
          ) : (
            <Button onClick={handleNext} variant="contained" color="primary">
              Next
            </Button>
          )}
        </Box>
      </Paper>
    </Container>
  );
};

// Question Field Component
interface QuestionFieldProps {
  question: Question;
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

const QuestionField: React.FC<QuestionFieldProps> = ({
  question,
  value,
  onChange,
  error,
}) => {
  return (
    <Box>
      <Typography variant="h6" component="label" htmlFor={question.id} gutterBottom>
        {question.question}
      </Typography>

      {question.type === 'select' && question.options && (
        <Box sx={{ mt: 2 }}>
          <select
            id={question.id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            style={{
              width: '100%',
              padding: '12px',
              fontSize: '16px',
              borderRadius: '4px',
              border: error ? '2px solid #d32f2f' : '1px solid #ccc',
            }}
            aria-label={question.question}
          >
            <option value="">Select an option...</option>
            {question.options.map((option) => (
              <option key={option} value={option}>
                {option.charAt(0).toUpperCase() + option.slice(1)}
              </option>
            ))}
          </select>
        </Box>
      )}

      {question.type === 'textarea' && (
        <Box sx={{ mt: 2 }}>
          <textarea
            id={question.id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={5}
            style={{
              width: '100%',
              padding: '12px',
              fontSize: '16px',
              borderRadius: '4px',
              border: error ? '2px solid #d32f2f' : '1px solid #ccc',
              fontFamily: 'inherit',
              resize: 'vertical',
            }}
            aria-label={question.question}
          />
          {question.minLength && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Minimum {question.minLength} characters
            </Typography>
          )}
        </Box>
      )}

      {question.type === 'text' && (
        <Box sx={{ mt: 2 }}>
          <input
            type="text"
            id={question.id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            style={{
              width: '100%',
              padding: '12px',
              fontSize: '16px',
              borderRadius: '4px',
              border: error ? '2px solid #d32f2f' : '1px solid #ccc',
            }}
            aria-label={question.question}
          />
        </Box>
      )}

      {error && (
        <Typography variant="body2" color="error" sx={{ mt: 1 }}>
          {error}
        </Typography>
      )}
    </Box>
  );
};

export default OnboardingPage;
