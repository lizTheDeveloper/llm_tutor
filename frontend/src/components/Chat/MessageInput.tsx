import React, { useState, KeyboardEvent, ChangeEvent } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Send } from '@mui/icons-material';

interface MessageInputProps {
  onSend: (message: string) => void;
  sending?: boolean;
  error?: string | null;
  maxLength?: number;
}

const MessageInput: React.FC<MessageInputProps> = ({
  onSend,
  sending = false,
  error = null,
  maxLength = 5000,
}) => {
  const [message, setMessage] = useState('');

  const handleSend = () => {
    const trimmedMessage = message.trim();
    if (trimmedMessage && !sending) {
      onSend(trimmedMessage);
      setMessage('');
    }
  };

  const handleKeyPress = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = event.target.value;
    if (newValue.length <= maxLength) {
      setMessage(newValue);
    }
  };

  const characterCount = message.length;
  const isNearMax = characterCount > maxLength * 0.9;

  return (
    <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
        <TextField
          fullWidth
          multiline
          maxRows={6}
          value={message}
          onChange={handleChange}
          onKeyPress={handleKeyPress}
          disabled={sending}
          placeholder="Type your message..."
          variant="outlined"
          inputProps={{
            'aria-label': 'Message input',
          }}
          sx={{
            '& .MuiOutlinedInput-root': {
              paddingRight: '8px',
            },
          }}
        />

        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={!message.trim() || sending}
          aria-label="Send message"
          sx={{
            width: 48,
            height: 48,
          }}
        >
          {sending ? (
            <CircularProgress size={24} role="progressbar" />
          ) : (
            <Send />
          )}
        </IconButton>
      </Box>

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mt: 1,
        }}
      >
        <Typography
          variant="caption"
          color={isNearMax ? 'error' : 'text.secondary'}
        >
          {characterCount} / {maxLength}
        </Typography>

        {sending && (
          <Typography variant="caption" color="text.secondary">
            Sending...
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default MessageInput;
