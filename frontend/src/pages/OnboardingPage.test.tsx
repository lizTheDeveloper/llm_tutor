/**
 * Integration tests for Onboarding Interview UI (C4)
 *
 * Test Strategy:
 * - Test real user interactions and API integrations
 * - Mock only external API calls (backend endpoints)
 * - Test complete user flows from start to finish
 * - Verify form validation and error handling
 * - Test save/resume functionality
 * - Ensure responsive design behavior
 *
 * Coverage:
 * - Multi-step form navigation (5 steps)
 * - Progress indicator updates
 * - Form validation on each step
 * - API integration for questions, status, and submission
 * - Save and resume partial completion
 * - Error handling and user feedback
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import OnboardingPage from './OnboardingPage';
import authReducer from '../store/slices/authSlice';
import profileReducer from '../store/slices/profileSlice';
import apiClient from '../services/api';

// Mock API client
vi.mock('../services/api');

const createMockStore = (initialState = {}) => {
  return configureStore({
    reducer: {
      auth: authReducer,
      profile: profileReducer,
    },
    preloadedState: {
      auth: {
        isAuthenticated: true,
        user: { id: 1, email: 'test@example.com', name: 'Test User' },
        token: 'mock-token',
        loading: false,
        error: null,
      },
      profile: {
        currentProfile: null,
        onboardingStatus: null,
        loading: false,
        error: null,
      },
      ...initialState,
    },
  });
};

const renderWithProviders = (
  component: React.ReactElement,
  store = createMockStore()
) => {
  return render(
    <Provider store={store}>
      <BrowserRouter>{component}</BrowserRouter>
    </Provider>
  );
};

describe('OnboardingPage - Multi-step Interview Flow', () => {
  // Helper to setup standard mocks for onboarding page
  const setupOnboardingMocks = (questionsData?: any, statusCompleted = false) => {
    const defaultQuestions = {
      questions: [
        {
          id: 'programming_language',
          question: 'What programming language would you like to learn?',
          type: 'select',
          options: ['python', 'javascript', 'java', 'typescript', 'go'],
        },
        {
          id: 'skill_level',
          question: 'What is your current skill level?',
          type: 'select',
          options: ['beginner', 'intermediate', 'advanced'],
        },
        {
          id: 'career_goals',
          question: 'What are your career goals?',
          type: 'textarea',
          minLength: 10,
          maxLength: 1000,
        },
        {
          id: 'learning_style',
          question: 'How do you prefer to learn?',
          type: 'select',
          options: ['hands-on', 'visual', 'reading', 'video'],
        },
        {
          id: 'time_commitment',
          question: 'How much time can you commit daily?',
          type: 'select',
          options: ['15-30 minutes', '30-60 minutes', '1-2 hours', '2+ hours'],
        },
      ],
      total_questions: 5,
      estimated_time: '5 minutes',
    };

    // Mock onboarding status check (first call)
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { onboarding_completed: statusCompleted, user_id: 1 },
    });

    // Mock questions fetch (second call) - only if not already completed
    if (!statusCompleted) {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: questionsData || defaultQuestions,
      });
    }

    return questionsData || defaultQuestions;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('Initial Load and Questions Fetch', () => {
    it('should fetch and display onboarding questions on mount', async () => {
      setupOnboardingMocks();

      renderWithProviders(<OnboardingPage />);

      // Check for loading state
      expect(screen.getByText(/loading/i)).toBeInTheDocument();

      // Wait for questions to load
      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify first question is displayed
      expect(
        screen.getByText(/what programming language would you like to learn/i)
      ).toBeInTheDocument();

      // Verify API was called
      expect(apiClient.get).toHaveBeenCalledWith('/v1/users/onboarding/questions');
    });

    it('should display error message if questions fetch fails', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce({
        response: { status: 500, data: { error: 'Server error' } },
      });

      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load.*questions/i)).toBeInTheDocument();
      });

      // Should show retry button
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('should check onboarding status and redirect if already completed', async () => {
      vi.mocked(apiClient.get).mockImplementation((url) => {
        if (url === '/v1/users/onboarding/status') {
          return Promise.resolve({
            data: {
              onboarding_completed: true,
              user_id: 1,
            },
          });
        }
        return Promise.reject(new Error('Not found'));
      });

      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        // Should redirect to dashboard (we'll verify navigation in E2E tests)
        expect(screen.queryByText(/programming language/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Progress Indicator', () => {
    it('should display progress indicator showing current step', async () => {
      const mockQuestions = {
        questions: Array(5).fill({}).map((_, index) => ({
          id: `question_${index}`,
          question: `Question ${index + 1}`,
          type: 'text',
        })),
        total_questions: 5,
        estimated_time: '5 minutes',
      };

      setupOnboardingMocks(mockQuestions);

      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/step 1 of 5/i)).toBeInTheDocument();
      });

      // Progress bar should show 20% (1/5)
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '20');
    });

    it('should update progress indicator when navigating between steps', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'lang',
            question: 'Choose language',
            type: 'select',
            options: ['python', 'javascript'],
          },
          {
            id: 'level',
            question: 'Choose level',
            type: 'select',
            options: ['beginner', 'intermediate'],
          },
        ],
        total_questions: 2,
        estimated_time: '2 minutes',
      };

      setupOnboardingMocks(mockQuestions);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/step 1 of 2/i)).toBeInTheDocument();
      });

      // Select an option and click next
      const selectField = screen.getByRole('combobox');
      await user.click(selectField);
      await user.click(screen.getByRole('option', { name: /python/i }));

      const nextButton = screen.getByRole('button', { name: /next/i });
      await user.click(nextButton);

      // Progress should update
      await waitFor(() => {
        expect(screen.getByText(/step 2 of 2/i)).toBeInTheDocument();
      });

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '100');
    });
  });

  describe('Form Validation', () => {
    it('should validate required fields before allowing next', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'career_goals',
            question: 'What are your career goals?',
            type: 'textarea',
            required: true,
            minLength: 10,
          },
        ],
        total_questions: 1,
        estimated_time: '1 minute',
      };

      setupOnboardingMocks(mockQuestions);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toBeInTheDocument();
      });

      // Try to click next without filling field
      const nextButton = screen.getByRole('button', { name: /next|submit/i });
      await user.click(nextButton);

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/this field is required/i)).toBeInTheDocument();
      });

      // Field should not advance
      expect(screen.getByText(/step 1 of 1/i)).toBeInTheDocument();
    });

    it('should validate minimum length for textarea fields', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'career_goals',
            question: 'What are your career goals?',
            type: 'textarea',
            minLength: 10,
          },
        ],
        total_questions: 1,
        estimated_time: '1 minute',
      };

      setupOnboardingMocks(mockQuestions);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toBeInTheDocument();
      });

      // Enter text less than minimum length
      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'short');

      const nextButton = screen.getByRole('button', { name: /next|submit/i });
      await user.click(nextButton);

      // Should show validation error
      await waitFor(() => {
        expect(
          screen.getByText(/must be at least 10 characters/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Multi-step Navigation', () => {
    const mockQuestions = {
      questions: [
        {
          id: 'programming_language',
          question: 'Choose your language',
          type: 'select',
          options: ['python', 'javascript'],
        },
        {
          id: 'skill_level',
          question: 'Choose your level',
          type: 'select',
          options: ['beginner', 'intermediate'],
        },
        {
          id: 'career_goals',
          question: 'Your career goals',
          type: 'textarea',
          minLength: 10,
        },
      ],
      total_questions: 3,
      estimated_time: '3 minutes',
    };

    it('should navigate forward through steps', async () => {
      setupOnboardingMocks(mockQuestions);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose your language/i)).toBeInTheDocument();
      });

      // Step 1: Select language
      const selectField = screen.getByRole('combobox');
      await user.click(selectField);
      await user.click(screen.getByRole('option', { name: /python/i }));

      await user.click(screen.getByRole('button', { name: /next/i }));

      // Should move to step 2
      await waitFor(() => {
        expect(screen.getByText(/choose your level/i)).toBeInTheDocument();
        expect(screen.getByText(/step 2 of 3/i)).toBeInTheDocument();
      });
    });

    it('should navigate backward through steps', async () => {
      setupOnboardingMocks(mockQuestions);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose your language/i)).toBeInTheDocument();
      });

      // Move to step 2
      const selectField = screen.getByRole('combobox');
      await user.click(selectField);
      await user.click(screen.getByRole('option', { name: /python/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));

      await waitFor(() => {
        expect(screen.getByText(/step 2 of 3/i)).toBeInTheDocument();
      });

      // Click back button
      const backButton = screen.getByRole('button', { name: /back/i });
      await user.click(backButton);

      // Should return to step 1
      await waitFor(() => {
        expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument();
        expect(screen.getByText(/choose your language/i)).toBeInTheDocument();
      });

      // Previous selection should be preserved
      expect(selectField).toHaveValue('python');
    });

    it('should disable back button on first step', async () => {
      setupOnboardingMocks(mockQuestions);

      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back/i });
      expect(backButton).toBeDisabled();
    });

    it('should show submit button on last step', async () => {
      setupOnboardingMocks(mockQuestions);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      // Navigate to last step
      await waitFor(() => {
        expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument();
      });

      // Step 1
      const selectField = screen.getByRole('combobox');
      await user.click(selectField);
      await user.click(screen.getByRole('option', { name: /python/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Step 2
      await waitFor(() => {
        expect(screen.getByText(/step 2 of 3/i)).toBeInTheDocument();
      });
      const selectField2 = screen.getByRole('combobox');
      await user.click(selectField2);
      await user.click(screen.getByRole('option', { name: /beginner/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Step 3 (last)
      await waitFor(() => {
        expect(screen.getByText(/step 3 of 3/i)).toBeInTheDocument();
      });

      // Should show submit button instead of next
      expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('should submit onboarding data and redirect on success', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'programming_language',
            question: 'Choose language',
            type: 'select',
            options: ['python'],
          },
          {
            id: 'skill_level',
            question: 'Choose level',
            type: 'select',
            options: ['beginner'],
          },
          {
            id: 'career_goals',
            question: 'Career goals',
            type: 'textarea',
            minLength: 10,
          },
          {
            id: 'learning_style',
            question: 'Learning style',
            type: 'select',
            options: ['hands-on'],
          },
          {
            id: 'time_commitment',
            question: 'Time commitment',
            type: 'select',
            options: ['1-2 hours'],
          },
        ],
        total_questions: 5,
        estimated_time: '5 minutes',
      };

      setupOnboardingMocks(mockQuestions);
      vi.mocked(apiClient.post).mockResolvedValueOnce({
        data: {
          user_id: 1,
          message: 'Onboarding completed successfully',
          onboarding_completed: true,
        },
      });

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose language/i)).toBeInTheDocument();
      });

      // Fill out all steps
      // Step 1
      const select1 = screen.getByRole('combobox');
      await user.click(select1);
      await user.click(screen.getByRole('option', { name: /python/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Step 2
      await waitFor(() => {
        expect(screen.getByText(/choose level/i)).toBeInTheDocument();
      });
      const select2 = screen.getByRole('combobox');
      await user.click(select2);
      await user.click(screen.getByRole('option', { name: /beginner/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Step 3
      await waitFor(() => {
        expect(screen.getByText(/career goals/i)).toBeInTheDocument();
      });
      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'I want to become a full-stack developer');
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Step 4
      await waitFor(() => {
        expect(screen.getByText(/learning style/i)).toBeInTheDocument();
      });
      const select3 = screen.getByRole('combobox');
      await user.click(select3);
      await user.click(screen.getByRole('option', { name: /hands-on/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Step 5 - Submit
      await waitFor(() => {
        expect(screen.getByText(/time commitment/i)).toBeInTheDocument();
      });
      const select4 = screen.getByRole('combobox');
      await user.click(select4);
      await user.click(screen.getByRole('option', { name: /1-2 hours/i }));

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      // Should call API with correct data
      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/v1/users/onboarding', {
          programming_language: 'python',
          skill_level: 'beginner',
          career_goals: 'I want to become a full-stack developer',
          learning_style: 'hands-on',
          time_commitment: '1-2 hours',
        });
      });

      // Should show success message
      await waitFor(() => {
        expect(
          screen.getByText(/onboarding completed successfully/i)
        ).toBeInTheDocument();
      });
    });

    it('should handle submission errors gracefully', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'programming_language',
            question: 'Choose language',
            type: 'select',
            options: ['python'],
          },
        ],
        total_questions: 1,
        estimated_time: '1 minute',
      };

      setupOnboardingMocks(mockQuestions);
      vi.mocked(apiClient.post).mockRejectedValueOnce({
        response: {
          status: 400,
          data: { error: 'Invalid programming language' },
        },
      });

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose language/i)).toBeInTheDocument();
      });

      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByRole('option', { name: /python/i }));

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      // Should show error message
      await waitFor(() => {
        expect(
          screen.getByText(/invalid programming language/i)
        ).toBeInTheDocument();
      });

      // Should still be on the same page (not redirected)
      expect(screen.getByText(/choose language/i)).toBeInTheDocument();
    });

    it('should show loading state during submission', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'programming_language',
            question: 'Choose language',
            type: 'select',
            options: ['python'],
          },
        ],
        total_questions: 1,
        estimated_time: '1 minute',
      };

      setupOnboardingMocks(mockQuestions);

      // Delay the response
      vi.mocked(apiClient.post).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve({
          data: { message: 'Success', onboarding_completed: true },
        }), 100))
      );

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose language/i)).toBeInTheDocument();
      });

      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByRole('option', { name: /python/i }));

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      // Should show loading state
      expect(screen.getByText(/submitting/i)).toBeInTheDocument();
      expect(submitButton).toBeDisabled();

      // Wait for completion
      await waitFor(() => {
        expect(screen.queryByText(/submitting/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Save and Resume Functionality', () => {
    it('should save progress to localStorage when navigating between steps', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'programming_language',
            question: 'Choose language',
            type: 'select',
            options: ['python'],
          },
          {
            id: 'skill_level',
            question: 'Choose level',
            type: 'select',
            options: ['beginner'],
          },
        ],
        total_questions: 2,
        estimated_time: '2 minutes',
      };

      setupOnboardingMocks(mockQuestions);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose language/i)).toBeInTheDocument();
      });

      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByRole('option', { name: /python/i }));
      await user.click(screen.getByRole('button', { name: /next/i }));

      // Check localStorage
      const savedProgress = localStorage.getItem('onboarding_progress');
      expect(savedProgress).toBeTruthy();

      const parsedProgress = JSON.parse(savedProgress!);
      expect(parsedProgress).toMatchObject({
        currentStep: 1,
        answers: {
          programming_language: 'python',
        },
      });
    });

    it('should resume from saved progress on page load', async () => {
      const savedProgress = {
        currentStep: 1,
        answers: {
          programming_language: 'python',
        },
      };

      localStorage.setItem('onboarding_progress', JSON.stringify(savedProgress));

      const mockQuestions = {
        questions: [
          {
            id: 'programming_language',
            question: 'Choose language',
            type: 'select',
            options: ['python'],
          },
          {
            id: 'skill_level',
            question: 'Choose level',
            type: 'select',
            options: ['beginner'],
          },
        ],
        total_questions: 2,
        estimated_time: '2 minutes',
      };

      setupOnboardingMocks(mockQuestions);

      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        // Should resume at step 2
        expect(screen.getByText(/step 2 of 2/i)).toBeInTheDocument();
        expect(screen.getByText(/choose level/i)).toBeInTheDocument();
      });
    });

    it('should clear saved progress after successful submission', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'programming_language',
            question: 'Choose language',
            type: 'select',
            options: ['python'],
          },
        ],
        total_questions: 1,
        estimated_time: '1 minute',
      };

      localStorage.setItem('onboarding_progress', JSON.stringify({ currentStep: 0 }));

      setupOnboardingMocks(mockQuestions);
      vi.mocked(apiClient.post).mockResolvedValueOnce({
        data: {
          message: 'Success',
          onboarding_completed: true,
        },
      });

      const user = userEvent.setup();
      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose language/i)).toBeInTheDocument();
      });

      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByRole('option', { name: /python/i }));
      await user.click(screen.getByRole('button', { name: /submit/i }));

      await waitFor(() => {
        expect(screen.getByText(/onboarding completed successfully/i)).toBeInTheDocument();
      });

      // localStorage should be cleared
      expect(localStorage.getItem('onboarding_progress')).toBeNull();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', async () => {
      const mockQuestions = {
        questions: [
          {
            id: 'programming_language',
            question: 'Choose your language',
            type: 'select',
            options: ['python'],
          },
        ],
        total_questions: 1,
        estimated_time: '1 minute',
      };

      setupOnboardingMocks(mockQuestions);

      renderWithProviders(<OnboardingPage />);

      await waitFor(() => {
        expect(screen.getByText(/choose your language/i)).toBeInTheDocument();
      });

      // Progress indicator should have proper ARIA attributes
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');

      // Form should have proper labeling
      const select = screen.getByRole('combobox');
      expect(select).toHaveAccessibleName(/choose your language/i);

      // Navigation buttons should be keyboard accessible
      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeVisible();
    });
  });
});
