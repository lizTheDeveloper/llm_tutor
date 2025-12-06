import React, { useState } from 'react';
import { Box, Paper, Typography, IconButton, Chip } from '@mui/material';
import { ContentCopy, Check } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import type { Message } from '../../store/slices/chatSlice';
import { format } from 'date-fns';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const isUser = message.role === 'user';

  // Format timestamp
  const formattedTime = format(new Date(message.created_at), 'h:mm a');

  // Handle copy to clipboard
  const handleCopyCode = async (code: string, identifier: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(identifier);
      setTimeout(() => setCopiedCode(null), 2000);
    } catch (error) {
      console.error('Failed to copy code:', error);
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      <Paper
        data-role={message.role}
        elevation={1}
        sx={{
          maxWidth: '75%',
          p: 2,
          backgroundColor: isUser ? 'primary.light' : 'grey.100',
          color: isUser ? 'primary.contrastText' : 'text.primary',
        }}
      >
        {/* Message content with markdown rendering */}
        <Box
          sx={{
            '& p': { m: 0, mb: 1 },
            '& p:last-child': { mb: 0 },
            '& pre': { m: 0, mb: 1 },
            '& ul, & ol': { m: 0, mb: 1, pl: 3 },
            '& li': { mb: 0.5 },
            '& code': {
              backgroundColor: isUser ? 'rgba(0,0,0,0.1)' : 'rgba(0,0,0,0.05)',
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '0.9em',
            },
            '& a': {
              color: isUser ? 'inherit' : 'primary.main',
              textDecoration: 'underline',
            },
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                const codeString = String(children).replace(/\n$/, '');
                const codeIdentifier = `${message.id}-${codeString.substring(0, 20)}`;

                if (!inline && match) {
                  // Code block with syntax highlighting
                  return (
                    <Box sx={{ position: 'relative', mb: 1 }}>
                      <IconButton
                        size="small"
                        aria-label="Copy code"
                        onClick={() => handleCopyCode(codeString, codeIdentifier)}
                        sx={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          zIndex: 1,
                          backgroundColor: 'rgba(255,255,255,0.1)',
                          '&:hover': {
                            backgroundColor: 'rgba(255,255,255,0.2)',
                          },
                        }}
                      >
                        {copiedCode === codeIdentifier ? (
                          <Check fontSize="small" />
                        ) : (
                          <ContentCopy fontSize="small" />
                        )}
                      </IconButton>
                      {copiedCode === codeIdentifier && (
                        <Typography
                          variant="caption"
                          sx={{
                            position: 'absolute',
                            top: 8,
                            right: 50,
                            color: 'success.main',
                            backgroundColor: 'background.paper',
                            px: 1,
                            py: 0.5,
                            borderRadius: 1,
                            zIndex: 1,
                          }}
                        >
                          Copied!
                        </Typography>
                      )}
                      <SyntaxHighlighter
                        {...props}
                        style={vscDarkPlus}
                        language={match[1]}
                        PreTag="div"
                      >
                        {codeString}
                      </SyntaxHighlighter>
                    </Box>
                  );
                } else {
                  // Inline code
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                }
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </Box>

        {/* Timestamp and metadata */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mt: 1,
            gap: 1,
            flexWrap: 'wrap',
          }}
        >
          <Typography
            variant="caption"
            sx={{
              color: isUser ? 'rgba(255,255,255,0.7)' : 'text.secondary',
            }}
          >
            {formattedTime}
          </Typography>

          {/* Show model and token info for assistant messages */}
          {!isUser && message.model_used && (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Chip
                label={message.model_used}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.7rem' }}
              />
              {message.tokens_used && (
                <Chip
                  label={`${message.tokens_used} tokens`}
                  size="small"
                  variant="outlined"
                  sx={{ height: 20, fontSize: '0.7rem' }}
                />
              )}
            </Box>
          )}
        </Box>
      </Paper>
    </Box>
  );
};

export default ChatMessage;
