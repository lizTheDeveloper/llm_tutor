/**
 * Test Suite for ChatPage Component
 *
 * Test Strategy:
 * - Test rendering of chat interface
 * - Test message sending and receiving
 * - Test conversation list display and switching
 * - Test integration with Redux store
 * - Test loading states
 * - Test error handling
 * - Test responsive layout
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { MemoryRouter } from 'react-router-dom';
import ChatPage from './ChatPage';
import chatReducer from '../store/slices/chatSlice';
import authReducer from '../store/slices/authSlice';
import profileReducer from '../store/slices/profileSlice';

const createMockStore = (initialState = {}) => {
  return configureStore({
    reducer: {
      chat: chatReducer,
      auth: authReducer,
      profile: profileReducer,
    },
    preloadedState: {
      auth: {
        user: { id: '1', email: 'test@example.com', name: 'Test User' },
        token: 'mock-token',
        isAuthenticated: true,
        loading: false,
        error: null,
      },
      chat: {
        conversations: [],
        currentConversation: null,
        messages: [],
        loading: false,
        sending: false,
        error: null,
      },
      profile: {
        profile: null,
        loading: false,
        error: null,
      },
      ...initialState,
    },
  });
};

const renderWithProviders = (ui: React.ReactElement, store: any) => {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </Provider>
  );
};

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Rendering', () => {
    it('should render chat page title', () => {
      const store = createMockStore();
      renderWithProviders(<ChatPage />, store);

      expect(screen.getByText(/chat/i)).toBeInTheDocument();
    });

    it('should render message input area', () => {
      const store = createMockStore();
      renderWithProviders(<ChatPage />, store);

      expect(screen.getByPlaceholderText(/type.*message/i)).toBeInTheDocument();
    });

    it('should render send button', () => {
      const store = createMockStore();
      renderWithProviders(<ChatPage />, store);

      expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
    });

    it('should show empty state when no messages', () => {
      const store = createMockStore();
      renderWithProviders(<ChatPage />, store);

      expect(screen.getByText(/start.*conversation/i) || screen.getByText(/no messages/i)).toBeInTheDocument();
    });
  });

  describe('Message Display', () => {
    it('should display existing messages', () => {
      const store = createMockStore({
        chat: {
          conversations: [],
          currentConversation: 1,
          messages: [
            {
              id: 1,
              role: 'user',
              content: 'Hello',
              created_at: '2025-12-06T10:00:00Z',
            },
            {
              id: 2,
              role: 'assistant',
              content: 'Hi there!',
              created_at: '2025-12-06T10:00:30Z',
            },
          ],
          loading: false,
          sending: false,
          error: null,
        },
      });

      renderWithProviders(<ChatPage />, store);

      expect(screen.getByText('Hello')).toBeInTheDocument();
      expect(screen.getByText('Hi there!')).toBeInTheDocument();
    });

    it('should distinguish between user and assistant messages', () => {
      const store = createMockStore({
        chat: {
          conversations: [],
          currentConversation: 1,
          messages: [
            {
              id: 1,
              role: 'user',
              content: 'User message',
              created_at: '2025-12-06T10:00:00Z',
            },
            {
              id: 2,
              role: 'assistant',
              content: 'Assistant message',
              created_at: '2025-12-06T10:00:30Z',
            },
          ],
          loading: false,
          sending: false,
          error: null,
        },
      });

      const { container } = renderWithProviders(<ChatPage />, store);

      const userMessage = container.querySelector('[data-role="user"]');
      const assistantMessage = container.querySelector('[data-role="assistant"]');

      expect(userMessage).toBeInTheDocument();
      expect(assistantMessage).toBeInTheDocument();
    });
  });

  describe('Conversation List', () => {
    it('should display conversation list', () => {
      const store = createMockStore({
        chat: {
          conversations: [
            {
              id: 1,
              title: 'Chat Session 1',
              message_count: 5,
              context_type: 'general',
              created_at: '2025-12-06T10:00:00Z',
              updated_at: '2025-12-06T10:30:00Z',
              last_message_at: '2025-12-06T10:30:00Z',
            },
            {
              id: 2,
              title: 'Python Help',
              message_count: 3,
              context_type: 'general',
              created_at: '2025-12-06T09:00:00Z',
              updated_at: '2025-12-06T09:15:00Z',
              last_message_at: '2025-12-06T09:15:00Z',
            },
          ],
          currentConversation: null,
          messages: [],
          loading: false,
          sending: false,
          error: null,
        },
      });

      renderWithProviders(<ChatPage />, store);

      expect(screen.getByText('Chat Session 1')).toBeInTheDocument();
      expect(screen.getByText('Python Help')).toBeInTheDocument();
    });

    it('should highlight current conversation', () => {
      const store = createMockStore({
        chat: {
          conversations: [
            {
              id: 1,
              title: 'Chat Session 1',
              message_count: 5,
              context_type: 'general',
              created_at: '2025-12-06T10:00:00Z',
              updated_at: '2025-12-06T10:30:00Z',
              last_message_at: '2025-12-06T10:30:00Z',
            },
          ],
          currentConversation: 1,
          messages: [],
          loading: false,
          sending: false,
          error: null,
        },
      });

      const { container } = renderWithProviders(<ChatPage />, store);

      const activeConversation = container.querySelector('[data-conversation-id="1"]');
      expect(activeConversation).toHaveClass(/selected|active/i);
    });
  });

  describe('Loading States', () => {
    it('should show loading indicator when fetching messages', () => {
      const store = createMockStore({
        chat: {
          conversations: [],
          currentConversation: null,
          messages: [],
          loading: true,
          sending: false,
          error: null,
        },
      });

      renderWithProviders(<ChatPage />, store);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should disable input while sending', () => {
      const store = createMockStore({
        chat: {
          conversations: [],
          currentConversation: null,
          messages: [],
          loading: false,
          sending: true,
          error: null,
        },
      });

      renderWithProviders(<ChatPage />, store);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      expect(textarea).toBeDisabled();
    });
  });

  describe('Error Handling', () => {
    it('should display error message when present', () => {
      const errorMessage = 'Failed to send message';
      const store = createMockStore({
        chat: {
          conversations: [],
          currentConversation: null,
          messages: [],
          loading: false,
          sending: false,
          error: errorMessage,
        },
      });

      renderWithProviders(<ChatPage />, store);

      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });

  describe('New Conversation', () => {
    it('should show button to start new conversation', () => {
      const store = createMockStore();
      renderWithProviders(<ChatPage />, store);

      expect(screen.getByRole('button', { name: /new.*conversation/i }) ||
             screen.getByRole('button', { name: /new.*chat/i })).toBeInTheDocument();
    });
  });

  describe('Responsive Layout', () => {
    it('should render in mobile layout', () => {
      const store = createMockStore();
      global.innerWidth = 375;
      global.dispatchEvent(new Event('resize'));

      const { container } = renderWithProviders(<ChatPage />, store);

      expect(container).toBeInTheDocument();
    });

    it('should render in desktop layout', () => {
      const store = createMockStore();
      global.innerWidth = 1920;
      global.dispatchEvent(new Event('resize'));

      const { container } = renderWithProviders(<ChatPage />, store);

      expect(container).toBeInTheDocument();
    });
  });
});
