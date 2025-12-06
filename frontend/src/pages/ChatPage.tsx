import React, { useEffect, useRef, useState } from 'react';
import {
  Box,
  Container,
  Grid,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  IconButton,
  Drawer,
  useMediaQuery,
  useTheme,
  CircularProgress,
  Button,
  Alert,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../hooks/useRedux';
import {
  sendMessage,
  fetchConversations,
  fetchConversation,
  deleteConversation,
  setCurrentConversation,
  clearError,
} from '../store/slices/chatSlice';
import ChatMessage from '../components/Chat/ChatMessage';
import MessageInput from '../components/Chat/MessageInput';
import { format } from 'date-fns';

const ChatPage: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const dispatch = useAppDispatch();

  const { conversations, currentConversation, messages, loading, sending, error } =
    useAppSelector((state) => state.chat);

  const [drawerOpen, setDrawerOpen] = useState(!isMobile);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load conversations on mount
  useEffect(() => {
    dispatch(fetchConversations());
  }, [dispatch]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Handle message send
  const handleSendMessage = async (message: string) => {
    dispatch(clearError());
    await dispatch(
      sendMessage({
        message,
        conversationId: currentConversation || undefined,
      })
    );
  };

  // Handle conversation selection
  const handleSelectConversation = async (conversationId: number) => {
    dispatch(setCurrentConversation(conversationId));
    await dispatch(fetchConversation(conversationId));
    if (isMobile) {
      setDrawerOpen(false);
    }
  };

  // Handle new conversation
  const handleNewConversation = () => {
    dispatch(setCurrentConversation(null));
    if (isMobile) {
      setDrawerOpen(false);
    }
  };

  // Handle delete conversation
  const handleDeleteConversation = async (
    conversationId: number,
    event: React.MouseEvent
  ) => {
    event.stopPropagation();
    if (confirm('Are you sure you want to delete this conversation?')) {
      await dispatch(deleteConversation(conversationId));
    }
  };

  // Conversation list sidebar
  const conversationList = (
    <Box sx={{ width: isMobile ? 280 : '100%', height: '100%' }}>
      <Box
        sx={{
          p: 2,
          borderBottom: 1,
          borderColor: 'divider',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h6">Conversations</Typography>
        <IconButton
          onClick={handleNewConversation}
          size="small"
          aria-label="New conversation"
        >
          <AddIcon />
        </IconButton>
      </Box>

      <List sx={{ overflow: 'auto', height: 'calc(100% - 73px)' }}>
        {conversations.length === 0 ? (
          <ListItem>
            <ListItemText
              primary="No conversations yet"
              secondary="Start a new conversation"
            />
          </ListItem>
        ) : (
          conversations.map((conversation) => (
            <ListItemButton
              key={conversation.id}
              selected={currentConversation === conversation.id}
              onClick={() => handleSelectConversation(conversation.id)}
              data-conversation-id={conversation.id}
              className={
                currentConversation === conversation.id ? 'selected' : ''
              }
            >
              <ListItemText
                primary={conversation.title}
                secondary={`${conversation.message_count} messages • ${format(
                  new Date(conversation.last_message_at),
                  'MMM d, h:mm a'
                )}`}
              />
              <IconButton
                edge="end"
                aria-label="Delete conversation"
                onClick={(e) => handleDeleteConversation(conversation.id, e)}
                size="small"
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </ListItemButton>
          ))
        )}
      </List>
    </Box>
  );

  return (
    <Container maxWidth="xl" sx={{ height: '100vh', py: 2 }}>
      <Grid container spacing={2} sx={{ height: '100%' }}>
        {/* Conversation List - Desktop */}
        {!isMobile && (
          <Grid item md={3} sx={{ height: '100%' }}>
            <Paper sx={{ height: '100%' }}>{conversationList}</Paper>
          </Grid>
        )}

        {/* Chat Area */}
        <Grid item xs={12} md={9} sx={{ height: '100%' }}>
          <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <Box
              sx={{
                p: 2,
                borderBottom: 1,
                borderColor: 'divider',
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              {isMobile && (
                <IconButton
                  onClick={() => setDrawerOpen(true)}
                  edge="start"
                  aria-label="Open menu"
                >
                  <MenuIcon />
                </IconButton>
              )}
              <Typography variant="h5">Chat with Your AI Tutor</Typography>
            </Box>

            {/* Messages Area */}
            <Box
              sx={{
                flexGrow: 1,
                overflow: 'auto',
                p: 2,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {loading && (
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                  }}
                >
                  <CircularProgress />
                </Box>
              )}

              {!loading && messages.length === 0 && (
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                  }}
                >
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      Start a conversation
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Ask me anything about programming!
                    </Typography>
                  </Box>
                </Box>
              )}

              {!loading &&
                messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}

              <div ref={messagesEndRef} />
            </Box>

            {/* Error Display */}
            {error && (
              <Alert severity="error" onClose={() => dispatch(clearError())}>
                {error}
              </Alert>
            )}

            {/* Message Input */}
            <MessageInput onSend={handleSendMessage} sending={sending} error={error} />
          </Paper>
        </Grid>
      </Grid>

      {/* Mobile Drawer */}
      {isMobile && (
        <Drawer
          anchor="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
        >
          {conversationList}
        </Drawer>
      )}
    </Container>
  );
};

export default ChatPage;
