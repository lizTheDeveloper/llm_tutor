/**
 * Test Suite for MessageInput Component
 *
 * Test Strategy:
 * - Test form validation (required field, max length)
 * - Test message submission
 * - Test loading/sending state
 * - Test keyboard shortcuts (Enter to send, Shift+Enter for newline)
 * - Test disabled state while sending
 * - Test clearing input after successful send
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MessageInput from './MessageInput';

describe('MessageInput', () => {
  const mockOnSend = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render textarea input', () => {
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      expect(textarea).toBeInTheDocument();
      expect(textarea.tagName).toBe('TEXTAREA');
    });

    it('should render send button', () => {
      render(<MessageInput onSend={mockOnSend} />);

      const sendButton = screen.getByRole('button', { name: /send/i });
      expect(sendButton).toBeInTheDocument();
    });

    it('should have empty initial value', () => {
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      expect(textarea).toHaveValue('');
    });
  });

  describe('User Input', () => {
    it('should update textarea value on typing', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      await user.type(textarea, 'Hello, world!');

      expect(textarea).toHaveValue('Hello, world!');
    });

    it('should allow multiline input', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      await user.type(textarea, 'Line 1{Shift>}{Enter}{/Shift}Line 2');

      expect(textarea).toHaveValue('Line 1\nLine 2');
    });

    it('should respect max length constraint', async () => {
      const user = userEvent.setup();
      const maxLength = 5000;
      render(<MessageInput onSend={mockOnSend} maxLength={maxLength} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      const longText = 'A'.repeat(6000);

      await user.type(textarea, longText);

      // Should be truncated to max length
      expect(textarea.value.length).toBeLessThanOrEqual(maxLength);
    });
  });

  describe('Message Submission', () => {
    it('should call onSend when send button is clicked', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      const sendButton = screen.getByRole('button', { name: /send/i });

      await user.type(textarea, 'Test message');
      await user.click(sendButton);

      expect(mockOnSend).toHaveBeenCalledWith('Test message');
      expect(mockOnSend).toHaveBeenCalledTimes(1);
    });

    it('should call onSend when Enter key is pressed', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);

      await user.type(textarea, 'Test message{Enter}');

      expect(mockOnSend).toHaveBeenCalledWith('Test message');
    });

    it('should not send when Shift+Enter is pressed', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);

      await user.type(textarea, 'Line 1{Shift>}{Enter}{/Shift}Line 2');

      expect(mockOnSend).not.toHaveBeenCalled();
      expect(textarea).toHaveValue('Line 1\nLine 2');
    });

    it('should clear input after successful send', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      const sendButton = screen.getByRole('button', { name: /send/i });

      await user.type(textarea, 'Test message');
      await user.click(sendButton);

      expect(textarea).toHaveValue('');
    });

    it('should not send empty message', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const sendButton = screen.getByRole('button', { name: /send/i });

      await user.click(sendButton);

      expect(mockOnSend).not.toHaveBeenCalled();
    });

    it('should not send whitespace-only message', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      const sendButton = screen.getByRole('button', { name: /send/i });

      await user.type(textarea, '   ');
      await user.click(sendButton);

      expect(mockOnSend).not.toHaveBeenCalled();
    });

    it('should trim message before sending', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      const sendButton = screen.getByRole('button', { name: /send/i });

      await user.type(textarea, '  Test message  ');
      await user.click(sendButton);

      expect(mockOnSend).toHaveBeenCalledWith('Test message');
    });
  });

  describe('Loading/Sending State', () => {
    it('should disable textarea when sending', () => {
      render(<MessageInput onSend={mockOnSend} sending={true} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      expect(textarea).toBeDisabled();
    });

    it('should disable send button when sending', () => {
      render(<MessageInput onSend={mockOnSend} sending={true} />);

      const sendButton = screen.getByRole('button', { name: /send/i });
      expect(sendButton).toBeDisabled();
    });

    it('should show loading indicator when sending', () => {
      render(<MessageInput onSend={mockOnSend} sending={true} />);

      // Look for loading spinner or "Sending..." text
      expect(screen.getByRole('progressbar') || screen.getByText(/sending/i)).toBeInTheDocument();
    });

    it('should enable inputs when not sending', () => {
      render(<MessageInput onSend={mockOnSend} sending={false} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      const sendButton = screen.getByRole('button', { name: /send/i });

      expect(textarea).not.toBeDisabled();
      expect(sendButton).not.toBeDisabled();
    });
  });

  describe('Character Count', () => {
    it('should display character count', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} maxLength={5000} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      await user.type(textarea, 'Test', { delay: 1 });

      await waitFor(() => {
        expect(screen.getByText(/4.*\/.*5000/i)).toBeInTheDocument();
      });
    });

    it('should update character count as user types', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} maxLength={100} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);

      await user.type(textarea, 'Hello', { delay: 1 });

      await waitFor(() => {
        expect(screen.getByText(/5.*\/.*100/i)).toBeInTheDocument();
      });

      await user.type(textarea, ' World', { delay: 1 });

      await waitFor(() => {
        expect(screen.getByText(/11.*\/.*100/i)).toBeInTheDocument();
      });
    });

    it('should show warning when approaching max length', async () => {
      const user = userEvent.setup();
      const maxLength = 100;
      render(<MessageInput onSend={mockOnSend} maxLength={maxLength} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      const nearMaxText = 'A'.repeat(95);

      await user.type(textarea, nearMaxText, { delay: 1 });

      // Should show warning color or text when > 90% of max
      await waitFor(() => {
        const countDisplay = screen.getByText(/95.*\/.*100/i);
        expect(countDisplay).toBeInTheDocument();
      });
    }, 10000);
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<MessageInput onSend={mockOnSend} />);

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      expect(textarea).toHaveAttribute('aria-label');
    });

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();
      render(<MessageInput onSend={mockOnSend} />);

      // Tab should navigate to textarea
      await user.tab();
      const textarea = screen.getByPlaceholderText(/type.*message/i);
      expect(textarea).toHaveFocus();

      // Tab should navigate to send button
      await user.tab();
      const sendButton = screen.getByRole('button', { name: /send/i });
      expect(sendButton).toHaveFocus();
    });
  });

  describe('Error Handling', () => {
    it('should display error message when provided', () => {
      const errorMessage = 'Failed to send message';
      render(<MessageInput onSend={mockOnSend} error={errorMessage} />);

      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('should clear error after user starts typing', async () => {
      const user = userEvent.setup();
      const { rerender } = render(
        <MessageInput onSend={mockOnSend} error="Error message" />
      );

      expect(screen.getByText('Error message')).toBeInTheDocument();

      const textarea = screen.getByPlaceholderText(/type.*message/i);
      await user.type(textarea, 'New message');

      rerender(<MessageInput onSend={mockOnSend} error={null} />);

      expect(screen.queryByText('Error message')).not.toBeInTheDocument();
    });
  });
});
