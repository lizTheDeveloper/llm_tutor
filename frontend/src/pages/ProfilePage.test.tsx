/**
 * Integration tests for Profile Display and Edit UI (C4)
 *
 * Test Strategy:
 * - Test profile data fetching and display
 * - Test profile editing functionality
 * - Test form validation for profile updates
 * - Mock only backend API calls
 * - Test responsive layout behavior
 *
 * Coverage:
 * - Profile data loading and display
 * - Edit mode toggle
 * - Profile update form validation
 * - API integration for GET and PUT profile
 * - Error handling for API failures
 * - Loading and success states
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import ProfilePage from './ProfilePage';
import authReducer from '../store/slices/authSlice';
import profileReducer from '../store/slices/profileSlice';
import apiClient from '../services/api';

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

const mockProfileData = {
  id: 1,
  email: 'test@example.com',
  name: 'Test User',
  avatar_url: null,
  bio: 'A passionate learner',
  programming_language: 'python',
  skill_level: 'intermediate',
  career_goals: 'Become a senior backend developer',
  learning_style: 'hands-on',
  time_commitment: '1-2 hours',
  role: 'student',
  is_active: true,
  is_mentor: false,
  current_streak: 5,
  longest_streak: 10,
  exercises_completed: 25,
  last_exercise_date: '2025-12-04T10:00:00Z',
  onboarding_completed: true,
  created_at: '2025-11-01T10:00:00Z',
  updated_at: '2025-12-05T10:00:00Z',
  last_login: '2025-12-05T09:00:00Z',
};

describe('ProfilePage - Display and Edit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Profile Display', () => {
    it('should fetch and display user profile on mount', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      renderWithProviders(<ProfilePage />);

      // Should show loading state
      expect(screen.getByText(/loading/i)).toBeInTheDocument();

      // Wait for profile to load
      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Verify profile data is displayed
      expect(screen.getByText('Test User')).toBeInTheDocument();
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
      expect(screen.getByText('A passionate learner')).toBeInTheDocument();
      expect(screen.getByText(/python/i)).toBeInTheDocument();
      expect(screen.getByText(/intermediate/i)).toBeInTheDocument();

      // Verify API was called
      expect(apiClient.get).toHaveBeenCalledWith('/v1/users/me');
    });

    it('should display progress statistics', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Check progress stats
      expect(screen.getByText(/5/)).toBeInTheDocument(); // current_streak
      expect(screen.getByText(/25/)).toBeInTheDocument(); // exercises_completed
      expect(screen.getByText(/10/)).toBeInTheDocument(); // longest_streak
    });

    it('should handle profile fetch errors', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce({
        response: {
          status: 500,
          data: { error: 'Server error' },
        },
      });

      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load profile/i)).toBeInTheDocument();
      });

      // Should show retry button
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('should display edit button when viewing own profile', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Edit button should be visible
      expect(screen.getByRole('button', { name: /edit profile/i })).toBeInTheDocument();
    });
  });

  describe('Profile Edit Mode', () => {
    it('should toggle to edit mode when edit button clicked', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      const editButton = screen.getByRole('button', { name: /edit profile/i });
      await user.click(editButton);

      // Should show editable fields
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/bio/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/programming language/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/skill level/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/career goals/i)).toBeInTheDocument();

      // Should show save and cancel buttons
      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();

      // Edit button should be hidden
      expect(
        screen.queryByRole('button', { name: /edit profile/i })
      ).not.toBeInTheDocument();
    });

    it('should populate form fields with current profile data', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      const editButton = screen.getByRole('button', { name: /edit profile/i });
      await user.click(editButton);

      // Check that fields are populated
      const nameField = screen.getByLabelText(/name/i) as HTMLInputElement;
      expect(nameField.value).toBe('Test User');

      const bioField = screen.getByLabelText(/bio/i) as HTMLTextAreaElement;
      expect(bioField.value).toBe('A passionate learner');

      const langField = screen.getByLabelText(/programming language/i) as HTMLSelectElement;
      expect(langField.value).toBe('python');
    });

    it('should cancel edit mode without saving changes', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Enter edit mode
      await user.click(screen.getByRole('button', { name: /edit profile/i }));

      // Modify a field
      const nameField = screen.getByLabelText(/name/i);
      await user.clear(nameField);
      await user.type(nameField, 'Changed Name');

      // Click cancel
      await user.click(screen.getByRole('button', { name: /cancel/i }));

      // Should return to display mode
      expect(screen.getByText('Test User')).toBeInTheDocument();
      expect(screen.queryByText('Changed Name')).not.toBeInTheDocument();

      // Edit button should be visible again
      expect(screen.getByRole('button', { name: /edit profile/i })).toBeInTheDocument();
    });
  });

  describe('Profile Update', () => {
    it('should update profile and show success message', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      const updatedProfile = {
        ...mockProfileData,
        name: 'Updated Name',
        bio: 'Updated bio',
      };

      vi.mocked(apiClient.put).mockResolvedValueOnce({
        data: {
          message: 'Profile updated successfully',
          profile: updatedProfile,
        },
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Enter edit mode
      await user.click(screen.getByRole('button', { name: /edit profile/i }));

      // Update fields
      const nameField = screen.getByLabelText(/name/i);
      await user.clear(nameField);
      await user.type(nameField, 'Updated Name');

      const bioField = screen.getByLabelText(/bio/i);
      await user.clear(bioField);
      await user.type(bioField, 'Updated bio');

      // Save changes
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Should call API with updated data
      await waitFor(() => {
        expect(apiClient.put).toHaveBeenCalledWith('/v1/users/me', {
          name: 'Updated Name',
          bio: 'Updated bio',
          programming_language: 'python',
          skill_level: 'intermediate',
          career_goals: 'Become a senior backend developer',
          learning_style: 'hands-on',
          time_commitment: '1-2 hours',
        });
      });

      // Should show success message
      await waitFor(() => {
        expect(
          screen.getByText(/profile updated successfully/i)
        ).toBeInTheDocument();
      });

      // Should return to display mode with updated data
      expect(screen.getByText('Updated Name')).toBeInTheDocument();
      expect(screen.getByText('Updated bio')).toBeInTheDocument();
    });

    it('should validate form fields before submission', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Enter edit mode
      await user.click(screen.getByRole('button', { name: /edit profile/i }));

      // Clear required field (name)
      const nameField = screen.getByLabelText(/name/i);
      await user.clear(nameField);

      // Try to save
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      });

      // API should not be called
      expect(apiClient.put).not.toHaveBeenCalled();
    });

    it('should validate career goals minimum length', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Enter edit mode
      await user.click(screen.getByRole('button', { name: /edit profile/i }));

      // Set career goals to less than 10 characters
      const goalsField = screen.getByLabelText(/career goals/i);
      await user.clear(goalsField);
      await user.type(goalsField, 'short');

      // Try to save
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Should show validation error
      await waitFor(() => {
        expect(
          screen.getByText(/must be at least 10 characters/i)
        ).toBeInTheDocument();
      });
    });

    it('should handle update errors gracefully', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      vi.mocked(apiClient.put).mockRejectedValueOnce({
        response: {
          status: 400,
          data: { error: 'Invalid data' },
        },
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Enter edit mode
      await user.click(screen.getByRole('button', { name: /edit profile/i }));

      // Make a change
      const nameField = screen.getByLabelText(/name/i);
      await user.clear(nameField);
      await user.type(nameField, 'New Name');

      // Try to save
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText(/invalid data/i)).toBeInTheDocument();
      });

      // Should remain in edit mode
      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    });

    it('should show loading state during update', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      // Delay the response
      vi.mocked(apiClient.put).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve({
          data: {
            message: 'Success',
            profile: mockProfileData,
          },
        }), 100))
      );

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Enter edit mode
      await user.click(screen.getByRole('button', { name: /edit profile/i }));

      const nameField = screen.getByLabelText(/name/i);
      await user.clear(nameField);
      await user.type(nameField, 'New Name');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      // Should show loading state
      expect(screen.getByText(/saving/i)).toBeInTheDocument();
      expect(saveButton).toBeDisabled();

      // Wait for completion
      await waitFor(() => {
        expect(screen.queryByText(/saving/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Responsive Display', () => {
    it('should display profile in card layout', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Should have profile sections
      expect(screen.getByText(/personal information/i)).toBeInTheDocument();
      expect(screen.getByText(/learning preferences/i)).toBeInTheDocument();
      expect(screen.getByText(/progress statistics/i)).toBeInTheDocument();
    });

    it('should display avatar placeholder if no avatar url', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Should show avatar with first letter of name
      const avatar = screen.getByTestId('user-avatar');
      expect(avatar).toHaveTextContent('T'); // First letter of "Test User"
    });

    it('should format dates correctly', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Should display formatted dates
      expect(screen.getByText(/member since/i)).toBeInTheDocument();
      expect(screen.getByText(/last active/i)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and structure', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      // Main content should have proper heading hierarchy
      const mainHeading = screen.getByRole('heading', { name: /test user/i });
      expect(mainHeading).toBeInTheDocument();

      // Edit button should be accessible
      const editButton = screen.getByRole('button', { name: /edit profile/i });
      expect(editButton).toBeVisible();
    });

    it('should have accessible form labels in edit mode', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockProfileData,
      });

      const user = userEvent.setup();
      renderWithProviders(<ProfilePage />);

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /edit profile/i }));

      // All form fields should have accessible names
      expect(screen.getByLabelText(/name/i)).toBeVisible();
      expect(screen.getByLabelText(/bio/i)).toBeVisible();
      expect(screen.getByLabelText(/programming language/i)).toBeVisible();
      expect(screen.getByLabelText(/skill level/i)).toBeVisible();
      expect(screen.getByLabelText(/career goals/i)).toBeVisible();
      expect(screen.getByLabelText(/learning style/i)).toBeVisible();
      expect(screen.getByLabelText(/time commitment/i)).toBeVisible();
    });
  });
});
