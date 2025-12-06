/**
 * Test Suite for Chat Redux Slice
 *
 * Test Strategy:
 * - Test all Redux state management for chat functionality
 * - Test async thunks for API integration (sendMessage, fetchConversations, etc.)
 * - Test state updates for loading, error, and success cases
 * - Mock API calls to test integration without external dependencies
 * - Test conversation management and message handling
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import chatReducer, {
  sendMessage,
  fetchConversations,
  fetchConversation,
  deleteConversation,
  setCurrentConversation,
  clearError,
  addOptimisticMessage,
  ChatState,
} from './chatSlice';
import { configureStore } from '@reduxjs/toolkit';
import axios from 'axios';

// Mock axios
vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

describe('chatSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create fresh store for each test
    store = configureStore({
      reducer: {
        chat: chatReducer,
      },
    });

    // Mock axios create to return mocked axios instance
    mockedAxios.create = vi.fn(() => mockedAxios as any);
  });

  describe('initial state', () => {
    it('should have correct initial state', () => {
      const state = store.getState().chat;

      expect(state.conversations).toEqual([]);
      expect(state.currentConversation).toBeNull();
      expect(state.messages).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.sending).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('synchronous actions', () => {
    it('should set current conversation', () => {
      const conversationId = 123;

      store.dispatch(setCurrentConversation(conversationId));
      const state = store.getState().chat;

      expect(state.currentConversation).toBe(conversationId);
      expect(state.messages).toEqual([]); // Messages cleared when switching conversations
    });

    it('should clear error', () => {
      // First set an error (we'll do this by failing an async operation)
      const initialState: ChatState = {
        conversations: [],
        currentConversation: null,
        messages: [],
        loading: false,
        sending: false,
        error: 'Test error',
      };

      const state = chatReducer(initialState, clearError());

      expect(state.error).toBeNull();
    });

    it('should add optimistic message', () => {
      const message = {
        id: 'temp-1',
        content: 'Test message',
        role: 'user' as const,
        created_at: new Date().toISOString(),
      };

      store.dispatch(addOptimisticMessage(message));
      const state = store.getState().chat;

      expect(state.messages).toHaveLength(1);
      expect(state.messages[0]).toEqual(message);
    });
  });

  describe('sendMessage async thunk', () => {
    const mockMessage = 'How do I implement a binary search?';
    const mockConversationId = 123;
    const mockResponse = {
      conversation_id: mockConversationId,
      message_id: 456,
      response: 'Let me help you understand binary search...',
      model: 'grok-2-1212',
      tokens_used: 150,
    };

    beforeEach(() => {
      // Mock localStorage
      const localStorageMock = {
        getItem: vi.fn(() => 'mock-token'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: vi.fn(),
      };
      global.localStorage = localStorageMock as any;
    });

    it('should send message successfully without conversation_id', async () => {
      mockedAxios.post = vi.fn().mockResolvedValue({
        data: mockResponse,
        status: 200,
      });

      await store.dispatch(
        sendMessage({ message: mockMessage })
      );

      const state = store.getState().chat;

      // Should set current conversation
      expect(state.currentConversation).toBe(mockConversationId);

      // Should add both user and assistant messages
      expect(state.messages).toHaveLength(2);
      expect(state.messages[0].role).toBe('user');
      expect(state.messages[0].content).toBe(mockMessage);
      expect(state.messages[1].role).toBe('assistant');
      expect(state.messages[1].content).toBe(mockResponse.response);

      // Should not be sending
      expect(state.sending).toBe(false);
      expect(state.error).toBeNull();
    });

    it('should send message successfully with conversation_id', async () => {
      // Set initial conversation
      store.dispatch(setCurrentConversation(mockConversationId));

      mockedAxios.post = vi.fn().mockResolvedValue({
        data: mockResponse,
        status: 200,
      });

      await store.dispatch(
        sendMessage({
          message: mockMessage,
          conversationId: mockConversationId,
        })
      );

      const state = store.getState().chat;

      expect(state.currentConversation).toBe(mockConversationId);
      expect(state.messages).toHaveLength(2);
      expect(state.sending).toBe(false);

      // Verify API was called with conversation_id
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/message'),
        expect.objectContaining({
          message: mockMessage,
          conversation_id: mockConversationId,
        }),
        expect.any(Object)
      );
    });

    it('should handle send message error', async () => {
      const errorMessage = 'Failed to send message';
      mockedAxios.post = vi.fn().mockRejectedValue({
        response: {
          data: { error: errorMessage },
          status: 500,
        },
      });

      await store.dispatch(
        sendMessage({ message: mockMessage })
      );

      const state = store.getState().chat;

      expect(state.sending).toBe(false);
      expect(state.error).toBe(errorMessage);
    });

    it('should set sending state while message is being sent', async () => {
      let resolvePromise: any;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockedAxios.post = vi.fn().mockReturnValue(promise);

      const dispatchPromise = store.dispatch(
        sendMessage({ message: mockMessage })
      );

      // Check sending state is true while promise is pending
      let state = store.getState().chat;
      expect(state.sending).toBe(true);

      // Resolve the promise
      resolvePromise({ data: mockResponse, status: 200 });
      await dispatchPromise;

      // Check sending state is false after resolution
      state = store.getState().chat;
      expect(state.sending).toBe(false);
    });
  });

  describe('fetchConversations async thunk', () => {
    const mockConversations = [
      {
        id: 1,
        title: 'Chat Session',
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
    ];

    beforeEach(() => {
      const localStorageMock = {
        getItem: vi.fn(() => 'mock-token'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: vi.fn(),
      };
      global.localStorage = localStorageMock as any;
    });

    it('should fetch conversations successfully', async () => {
      mockedAxios.get = vi.fn().mockResolvedValue({
        data: {
          conversations: mockConversations,
          total: 2,
          limit: 20,
          offset: 0,
        },
        status: 200,
      });

      await store.dispatch(fetchConversations());

      const state = store.getState().chat;

      expect(state.conversations).toEqual(mockConversations);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });

    it('should handle fetch conversations error', async () => {
      const errorMessage = 'Failed to fetch conversations';
      mockedAxios.get = vi.fn().mockRejectedValue({
        response: {
          data: { error: errorMessage },
          status: 500,
        },
      });

      await store.dispatch(fetchConversations());

      const state = store.getState().chat;

      expect(state.conversations).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.error).toBe(errorMessage);
    });
  });

  describe('fetchConversation async thunk', () => {
    const conversationId = 123;
    const mockMessages = [
      {
        id: 1,
        role: 'user',
        content: 'How do I use recursion?',
        tokens_used: null,
        model_used: null,
        created_at: '2025-12-06T10:00:00Z',
        metadata: null,
      },
      {
        id: 2,
        role: 'assistant',
        content: 'Recursion is a technique...',
        tokens_used: 100,
        model_used: 'grok-2-1212',
        created_at: '2025-12-06T10:00:30Z',
        metadata: { provider: 'groq' },
      },
    ];

    beforeEach(() => {
      const localStorageMock = {
        getItem: vi.fn(() => 'mock-token'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: vi.fn(),
      };
      global.localStorage = localStorageMock as any;
    });

    it('should fetch conversation messages successfully', async () => {
      mockedAxios.get = vi.fn().mockResolvedValue({
        data: {
          conversation: {
            id: conversationId,
            title: 'Chat Session',
            message_count: 2,
            context_type: 'general',
            created_at: '2025-12-06T10:00:00Z',
            updated_at: '2025-12-06T10:00:30Z',
          },
          messages: mockMessages,
        },
        status: 200,
      });

      await store.dispatch(fetchConversation(conversationId));

      const state = store.getState().chat;

      expect(state.messages).toEqual(mockMessages);
      expect(state.currentConversation).toBe(conversationId);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });

    it('should handle fetch conversation error', async () => {
      const errorMessage = 'Conversation not found';
      mockedAxios.get = vi.fn().mockRejectedValue({
        response: {
          data: { error: errorMessage },
          status: 404,
        },
      });

      await store.dispatch(fetchConversation(conversationId));

      const state = store.getState().chat;

      expect(state.messages).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.error).toBe(errorMessage);
    });
  });

  describe('deleteConversation async thunk', () => {
    const conversationId = 123;

    beforeEach(() => {
      const localStorageMock = {
        getItem: vi.fn(() => 'mock-token'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: vi.fn(),
      };
      global.localStorage = localStorageMock as any;

      // Set up initial state with conversations
      const mockConversations = [
        {
          id: conversationId,
          title: 'Chat Session',
          message_count: 5,
          context_type: 'general',
          created_at: '2025-12-06T10:00:00Z',
          updated_at: '2025-12-06T10:30:00Z',
          last_message_at: '2025-12-06T10:30:00Z',
        },
        {
          id: 456,
          title: 'Python Help',
          message_count: 3,
          context_type: 'general',
          created_at: '2025-12-06T09:00:00Z',
          updated_at: '2025-12-06T09:15:00Z',
          last_message_at: '2025-12-06T09:15:00Z',
        },
      ];

      mockedAxios.get = vi.fn().mockResolvedValue({
        data: { conversations: mockConversations },
        status: 200,
      });

      store.dispatch(fetchConversations());
    });

    it('should delete conversation successfully', async () => {
      mockedAxios.delete = vi.fn().mockResolvedValue({
        data: {
          message: 'Conversation deleted successfully',
          conversation_id: conversationId,
        },
        status: 200,
      });

      await store.dispatch(deleteConversation(conversationId));

      const state = store.getState().chat;

      // Should remove conversation from list
      expect(state.conversations.find((c) => c.id === conversationId)).toBeUndefined();
      expect(state.conversations).toHaveLength(1);
      expect(state.error).toBeNull();
    });

    it('should handle delete conversation error', async () => {
      const errorMessage = 'Failed to delete conversation';
      mockedAxios.delete = vi.fn().mockRejectedValue({
        response: {
          data: { error: errorMessage },
          status: 500,
        },
      });

      await store.dispatch(deleteConversation(conversationId));

      const state = store.getState().chat;

      expect(state.error).toBe(errorMessage);
      // Conversation should still exist
      expect(state.conversations.find((c) => c.id === conversationId)).toBeDefined();
    });
  });
});
