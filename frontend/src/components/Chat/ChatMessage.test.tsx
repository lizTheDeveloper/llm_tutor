/**
 * Test Suite for ChatMessage Component
 *
 * Test Strategy:
 * - Test rendering of user and assistant messages
 * - Test markdown rendering in message content
 * - Test syntax highlighting for code blocks
 * - Test copy-to-clipboard functionality
 * - Test message timestamps
 * - Test styling differences between user and assistant messages
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatMessage from './ChatMessage';
import type { Message } from '../../store/slices/chatSlice';

describe('ChatMessage', () => {
  const mockUserMessage: Message = {
    id: 1,
    role: 'user',
    content: 'How do I implement a binary search?',
    created_at: '2025-12-06T10:00:00Z',
  };

  const mockAssistantMessage: Message = {
    id: 2,
    role: 'assistant',
    content: 'A binary search is an efficient algorithm...',
    created_at: '2025-12-06T10:00:30Z',
    tokens_used: 100,
    model_used: 'grok-2-1212',
  };

  const mockMessageWithCode: Message = {
    id: 3,
    role: 'assistant',
    content: `Here's an example:

\`\`\`python
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
\`\`\`

This function searches for a target value in a sorted array.`,
    created_at: '2025-12-06T10:01:00Z',
    tokens_used: 150,
    model_used: 'grok-2-1212',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('User Messages', () => {
    it('should render user message content', () => {
      render(<ChatMessage message={mockUserMessage} />);

      expect(screen.getByText(mockUserMessage.content)).toBeInTheDocument();
    });

    it('should apply user message styling', () => {
      const { container } = render(<ChatMessage message={mockUserMessage} />);

      const messageBox = container.querySelector('[data-role="user"]');
      expect(messageBox).toBeInTheDocument();
    });

    it('should display user message timestamp', () => {
      render(<ChatMessage message={mockUserMessage} />);

      // Timestamp should be formatted (e.g., "10:00 AM")
      expect(screen.getByText(/10:00/i)).toBeInTheDocument();
    });

    it('should not show model information for user messages', () => {
      render(<ChatMessage message={mockUserMessage} />);

      expect(screen.queryByText(/grok/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/tokens/i)).not.toBeInTheDocument();
    });
  });

  describe('Assistant Messages', () => {
    it('should render assistant message content', () => {
      render(<ChatMessage message={mockAssistantMessage} />);

      expect(screen.getByText(/efficient algorithm/i)).toBeInTheDocument();
    });

    it('should apply assistant message styling', () => {
      const { container } = render(<ChatMessage message={mockAssistantMessage} />);

      const messageBox = container.querySelector('[data-role="assistant"]');
      expect(messageBox).toBeInTheDocument();
    });

    it('should display assistant message timestamp', () => {
      render(<ChatMessage message={mockAssistantMessage} />);

      expect(screen.getByText(/10:00/i)).toBeInTheDocument();
    });

    it('should show model information when available', () => {
      render(<ChatMessage message={mockAssistantMessage} />);

      expect(screen.getByText(/grok-2-1212/i)).toBeInTheDocument();
    });

    it('should show token usage when available', () => {
      render(<ChatMessage message={mockAssistantMessage} />);

      expect(screen.getByText(/100.*tokens?/i)).toBeInTheDocument();
    });
  });

  describe('Markdown Rendering', () => {
    it('should render markdown bold text', () => {
      const messageWithBold: Message = {
        id: 4,
        role: 'assistant',
        content: 'This is **bold text** in markdown',
        created_at: '2025-12-06T10:02:00Z',
      };

      const { container } = render(<ChatMessage message={messageWithBold} />);

      const boldElement = container.querySelector('strong');
      expect(boldElement).toBeInTheDocument();
      expect(boldElement?.textContent).toBe('bold text');
    });

    it('should render markdown italic text', () => {
      const messageWithItalic: Message = {
        id: 5,
        role: 'assistant',
        content: 'This is *italic text* in markdown',
        created_at: '2025-12-06T10:02:00Z',
      };

      const { container } = render(<ChatMessage message={messageWithItalic} />);

      const italicElement = container.querySelector('em');
      expect(italicElement).toBeInTheDocument();
      expect(italicElement?.textContent).toBe('italic text');
    });

    it('should render markdown links', () => {
      const messageWithLink: Message = {
        id: 6,
        role: 'assistant',
        content: 'Check out [this resource](https://example.com)',
        created_at: '2025-12-06T10:02:00Z',
      };

      render(<ChatMessage message={messageWithLink} />);

      const link = screen.getByRole('link', { name: /this resource/i });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', 'https://example.com');
    });

    it('should render markdown lists', () => {
      const messageWithList: Message = {
        id: 7,
        role: 'assistant',
        content: `Here are the steps:

- Step 1
- Step 2
- Step 3`,
        created_at: '2025-12-06T10:02:00Z',
      };

      const { container } = render(<ChatMessage message={messageWithList} />);

      const listItems = container.querySelectorAll('li');
      expect(listItems).toHaveLength(3);
      expect(listItems[0].textContent).toBe('Step 1');
      expect(listItems[1].textContent).toBe('Step 2');
      expect(listItems[2].textContent).toBe('Step 3');
    });
  });

  describe('Code Blocks and Syntax Highlighting', () => {
    it('should render inline code', () => {
      const messageWithInlineCode: Message = {
        id: 8,
        role: 'assistant',
        content: 'Use the `print()` function to output text',
        created_at: '2025-12-06T10:02:00Z',
      };

      const { container } = render(<ChatMessage message={messageWithInlineCode} />);

      const codeElement = container.querySelector('code');
      expect(codeElement).toBeInTheDocument();
      expect(codeElement?.textContent).toBe('print()');
    });

    it('should render code blocks with syntax highlighting', () => {
      const { container } = render(<ChatMessage message={mockMessageWithCode} />);

      // Should have a pre > code structure
      const preElement = container.querySelector('pre');
      expect(preElement).toBeInTheDocument();

      const codeElement = preElement?.querySelector('code');
      expect(codeElement).toBeInTheDocument();
    });

    it('should identify language from code fence', () => {
      const { container } = render(<ChatMessage message={mockMessageWithCode} />);

      // Code block should have language class
      const codeElement = container.querySelector('code');
      expect(codeElement?.className).toMatch(/python/i);
    });

    it('should display copy button for code blocks', () => {
      render(<ChatMessage message={mockMessageWithCode} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      expect(copyButton).toBeInTheDocument();
    });

    it('should copy code to clipboard when copy button is clicked', async () => {
      const user = userEvent.setup();

      // Mock clipboard API
      const mockWriteText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', {
        value: {
          writeText: mockWriteText,
        },
        writable: true,
        configurable: true,
      });

      render(<ChatMessage message={mockMessageWithCode} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      await user.click(copyButton);

      await waitFor(() => {
        expect(mockWriteText).toHaveBeenCalledWith(
          expect.stringContaining('def binary_search')
        );
      });
    });

    it('should show "Copied!" feedback after copying', async () => {
      const user = userEvent.setup();

      // Mock clipboard API
      Object.defineProperty(navigator, 'clipboard', {
        value: {
          writeText: vi.fn().mockResolvedValue(undefined),
        },
        writable: true,
        configurable: true,
      });

      render(<ChatMessage message={mockMessageWithCode} />);

      const copyButton = screen.getByRole('button', { name: /copy/i });
      await user.click(copyButton);

      await waitFor(() => {
        expect(screen.getByText(/copied/i)).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty message content', () => {
      const emptyMessage: Message = {
        id: 9,
        role: 'user',
        content: '',
        created_at: '2025-12-06T10:03:00Z',
      };

      const { container } = render(<ChatMessage message={emptyMessage} />);

      expect(container).toBeInTheDocument();
    });

    it('should handle very long messages', () => {
      const longContent = 'A'.repeat(10000);
      const longMessage: Message = {
        id: 10,
        role: 'assistant',
        content: longContent,
        created_at: '2025-12-06T10:03:00Z',
      };

      render(<ChatMessage message={longMessage} />);

      expect(screen.getByText(longContent)).toBeInTheDocument();
    });

    it('should handle special characters in content', () => {
      const messageWithSpecialChars: Message = {
        id: 11,
        role: 'assistant',
        content: 'Special chars: <>&"\'',
        created_at: '2025-12-06T10:03:00Z',
      };

      render(<ChatMessage message={messageWithSpecialChars} />);

      expect(screen.getByText(/Special chars/)).toBeInTheDocument();
    });
  });
});
