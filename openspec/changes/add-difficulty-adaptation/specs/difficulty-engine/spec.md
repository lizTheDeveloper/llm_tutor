# Difficulty Adaptation Engine Specification

## ADDED Requirements

### Requirement: Difficulty Scoring
The system SHALL calculate and maintain a difficulty score for each user based on performance.

#### Scenario: Initial difficulty score
- **WHEN** new user completes onboarding
- **THEN** set initial difficulty score based on self-assessed skill level

#### Scenario: Score update after success
- **WHEN** user completes exercise with >80% accuracy in good time
- **THEN** increase difficulty score slightly

#### Scenario: Score update after struggle
- **WHEN** user takes multiple attempts or exceeds expected time
- **THEN** decrease difficulty score slightly

### Requirement: Adaptive Exercise Selection
The system SHALL recommend exercises matching the user's current difficulty score.

#### Scenario: Difficulty matching
- **WHEN** generating daily exercise
- **THEN** select exercise with difficulty level matching user's score ±0.5

#### Scenario: Gradual progression
- **WHEN** user consistently succeeds
- **THEN** gradually increase recommended difficulty over time

#### Scenario: Skill plateau detection
- **WHEN** user difficulty score stable for N exercises
- **THEN** introduce variety in exercise types while maintaining difficulty

### Requirement: Performance Thresholds
The system SHALL use configurable thresholds to determine difficulty adjustments.

#### Scenario: Fast completion threshold
- **WHEN** completion time < 50% of expected
- **THEN** consider exercise too easy

#### Scenario: Slow completion threshold
- **WHEN** completion time > 150% of expected
- **THEN** consider exercise too hard

#### Scenario: Accuracy threshold
- **WHEN** accuracy < 70%
- **THEN** recommend easier exercises

### Requirement: Difficulty Bounds
The system SHALL enforce minimum and maximum difficulty limits.

#### Scenario: Minimum difficulty
- **WHEN** calculating new difficulty
- **THEN** ensure score never drops below configured minimum

#### Scenario: Maximum difficulty
- **WHEN** calculating new difficulty
- **THEN** ensure score never exceeds configured maximum

### Requirement: Smoothing and Stability
The system SHALL apply smoothing to prevent erratic difficulty changes.

#### Scenario: Exponential smoothing
- **WHEN** updating difficulty score
- **THEN** use exponential moving average with weight factor 0.3

#### Scenario: Minimum adjustment increment
- **WHEN** applying difficulty change
- **THEN** enforce minimum change of 0.1 to prevent micro-adjustments
