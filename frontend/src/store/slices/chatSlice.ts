import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Types
export interface Message {
  id: number | string;
  role: 'user' | 'assistant';
  content: string;
  tokens_used?: number | null;
  model_used?: string | null;
  created_at: string;
  metadata?: any;
}

export interface Conversation {
  id: number;
  title: string;
  message_count: number;
  context_type: string;
  created_at: string;
  updated_at: string;
  last_message_at: string;
}

export interface ChatState {
  conversations: Conversation[];
  currentConversation: number | null;
  messages: Message[];
  loading: boolean;
  sending: boolean;
  error: string | null;
}

// API client setup
const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
};

// Async Thunks
export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async (
    { message, conversationId }: { message: string; conversationId?: number },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/chat/message`,
        {
          message,
          conversation_id: conversationId,
        },
        getAuthHeaders()
      );

      return {
        conversationId: response.data.conversation_id,
        messageId: response.data.message_id,
        response: response.data.response,
        model: response.data.model,
        tokensUsed: response.data.tokens_used,
        userMessage: message,
      };
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to send message'
      );
    }
  }
);

export const fetchConversations = createAsyncThunk(
  'chat/fetchConversations',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/chat/conversations`,
        getAuthHeaders()
      );

      return response.data.conversations;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to fetch conversations'
      );
    }
  }
);

export const fetchConversation = createAsyncThunk(
  'chat/fetchConversation',
  async (conversationId: number, { rejectWithValue }) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/chat/conversations/${conversationId}`,
        getAuthHeaders()
      );

      return {
        conversationId,
        messages: response.data.messages,
      };
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to fetch conversation'
      );
    }
  }
);

export const deleteConversation = createAsyncThunk(
  'chat/deleteConversation',
  async (conversationId: number, { rejectWithValue }) => {
    try {
      await axios.delete(
        `${API_BASE_URL}/chat/conversations/${conversationId}`,
        getAuthHeaders()
      );

      return conversationId;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to delete conversation'
      );
    }
  }
);

// Initial State
const initialState: ChatState = {
  conversations: [],
  currentConversation: null,
  messages: [],
  loading: false,
  sending: false,
  error: null,
};

// Slice
const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    setCurrentConversation: (state, action: PayloadAction<number | null>) => {
      state.currentConversation = action.payload;
      state.messages = []; // Clear messages when switching conversations
    },
    clearError: (state) => {
      state.error = null;
    },
    addOptimisticMessage: (state, action: PayloadAction<Message>) => {
      state.messages.push(action.payload);
    },
    clearMessages: (state) => {
      state.messages = [];
    },
  },
  extraReducers: (builder) => {
    // sendMessage
    builder
      .addCase(sendMessage.pending, (state) => {
        state.sending = true;
        state.error = null;
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.sending = false;
        state.currentConversation = action.payload.conversationId;

        // Add user message
        const userMessage: Message = {
          id: `user-${Date.now()}`,
          role: 'user',
          content: action.payload.userMessage,
          created_at: new Date().toISOString(),
        };
        state.messages.push(userMessage);

        // Add assistant message
        const assistantMessage: Message = {
          id: action.payload.messageId,
          role: 'assistant',
          content: action.payload.response,
          tokens_used: action.payload.tokensUsed,
          model_used: action.payload.model,
          created_at: new Date().toISOString(),
        };
        state.messages.push(assistantMessage);
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.sending = false;
        state.error = action.payload as string;
      });

    // fetchConversations
    builder
      .addCase(fetchConversations.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchConversations.fulfilled, (state, action) => {
        state.loading = false;
        state.conversations = action.payload;
      })
      .addCase(fetchConversations.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });

    // fetchConversation
    builder
      .addCase(fetchConversation.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchConversation.fulfilled, (state, action) => {
        state.loading = false;
        state.currentConversation = action.payload.conversationId;
        state.messages = action.payload.messages;
      })
      .addCase(fetchConversation.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });

    // deleteConversation
    builder
      .addCase(deleteConversation.pending, (state) => {
        state.error = null;
      })
      .addCase(deleteConversation.fulfilled, (state, action) => {
        state.conversations = state.conversations.filter(
          (conv) => conv.id !== action.payload
        );
        // Clear current conversation if it was deleted
        if (state.currentConversation === action.payload) {
          state.currentConversation = null;
          state.messages = [];
        }
      })
      .addCase(deleteConversation.rejected, (state, action) => {
        state.error = action.payload as string;
      });
  },
});

export const {
  setCurrentConversation,
  clearError,
  addOptimisticMessage,
  clearMessages,
} = chatSlice.actions;

export default chatSlice.reducer;
