# Chat UI Specification

## ADDED Requirements

### Requirement: Chat Interface Layout
The system SHALL provide a chat interface with a main conversation area and optional sidebar for conversation history.

#### Scenario: Desktop layout
- **WHEN** user accesses chat on desktop (>1024px width)
- **THEN** display sidebar and main chat area side-by-side

#### Scenario: Mobile layout
- **WHEN** user accesses chat on mobile (<768px width)
- **THEN** display full-screen chat with collapsible sidebar

### Requirement: Message Display
The system SHALL display messages with clear visual differentiation between user and tutor messages.

#### Scenario: User message display
- **WHEN** user sends a message
- **THEN** display message right-aligned with distinct background color

#### Scenario: Tutor message display
- **WHEN** LLM tutor responds
- **THEN** display message left-aligned with tutor avatar and styling

#### Scenario: Message ordering
- **WHEN** viewing conversation
- **THEN** messages SHALL be ordered chronologically with timestamps

### Requirement: Message Input
The system SHALL provide a message input component with validation and submission controls.

#### Scenario: Valid message submission
- **WHEN** user types message and presses send
- **THEN** message is submitted to API and input is cleared

#### Scenario: Empty message prevention
- **WHEN** user attempts to send empty message
- **THEN** submission is blocked and input shows validation error

#### Scenario: Multi-line input
- **WHEN** user presses Shift+Enter
- **THEN** insert newline in input (don't submit)

#### Scenario: Submit shortcut
- **WHEN** user presses Enter (without Shift)
- **THEN** submit message

### Requirement: Code Syntax Highlighting
The system SHALL render code blocks with syntax highlighting using Prism.js.

#### Scenario: Code block rendering
- **WHEN** LLM response contains markdown code fence
- **THEN** render code with appropriate syntax highlighting

#### Scenario: Language detection
- **WHEN** code fence specifies language (e.g., ```python)
- **THEN** apply language-specific highlighting

#### Scenario: Copy to clipboard
- **WHEN** user clicks copy button on code block
- **THEN** copy code to clipboard and show confirmation

### Requirement: Markdown Rendering
The system SHALL render markdown formatting in LLM tutor messages.

#### Scenario: Bold and italic rendering
- **WHEN** message contains **bold** or *italic* markdown
- **THEN** render with appropriate formatting

#### Scenario: Lists rendering
- **WHEN** message contains bullet or numbered lists
- **THEN** render as HTML list elements

#### Scenario: Links rendering
- **WHEN** message contains markdown links
- **THEN** render as clickable hyperlinks

### Requirement: Loading States
The system SHALL display appropriate loading indicators during LLM processing.

#### Scenario: Typing indicator
- **WHEN** message is submitted and waiting for response
- **THEN** display typing indicator with tutor avatar

#### Scenario: Send button loading
- **WHEN** message is being sent
- **THEN** disable send button and show loading spinner

### Requirement: Conversation History
The system SHALL display a list of previous conversations and allow switching between them.

#### Scenario: Conversation list display
- **WHEN** user opens chat interface
- **THEN** display list of previous conversations in sidebar

#### Scenario: Conversation switching
- **WHEN** user clicks on a conversation
- **THEN** load and display that conversation's messages

#### Scenario: New conversation
- **WHEN** user clicks "New Chat" button
- **THEN** start fresh conversation and clear message list

### Requirement: Auto-scroll Behavior
The system SHALL automatically scroll to show the latest message.

#### Scenario: New message scroll
- **WHEN** new message is added to conversation
- **THEN** scroll message list to bottom

#### Scenario: Manual scroll preservation
- **WHEN** user manually scrolls up to view history
- **THEN** do not auto-scroll on new messages (preserve position)

### Requirement: Error Handling
The system SHALL display appropriate error messages when API calls fail.

#### Scenario: Network error
- **WHEN** message submission fails due to network error
- **THEN** display error message and allow retry

#### Scenario: API error response
- **WHEN** API returns error response
- **THEN** display error message with details from API

### Requirement: Mobile Responsiveness
The system SHALL adapt layout and interactions for mobile devices.

#### Scenario: Touch-friendly controls
- **WHEN** user interacts on touch device
- **THEN** all buttons and controls have minimum 44px touch target

#### Scenario: Sidebar toggle
- **WHEN** user on mobile taps menu icon
- **THEN** toggle conversation history sidebar

#### Scenario: Keyboard handling
- **WHEN** mobile keyboard appears
- **THEN** adjust chat layout to keep input visible
