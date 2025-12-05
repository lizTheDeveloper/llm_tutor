"""
Prompt template system for CodeMentor LLM interactions.
Provides reusable, parameterized prompts for various use cases.
"""
from typing import Dict, Any, Optional
from enum import Enum


class PromptType(Enum):
    """Types of prompts available in the system."""
    TUTOR_GREETING = "tutor_greeting"
    EXERCISE_GENERATION = "exercise_generation"
    CODE_REVIEW = "code_review"
    HINT_GENERATION = "hint_generation"
    FEEDBACK_GENERATION = "feedback_generation"
    ONBOARDING_INTERVIEW = "onboarding_interview"
    CONCEPT_EXPLANATION = "concept_explanation"


class PromptTemplateManager:
    """Manages prompt templates for LLM interactions."""

    # System prompts for different contexts
    SYSTEM_PROMPTS = {
        PromptType.TUTOR_GREETING: """You are a friendly and encouraging coding tutor for CodeMentor platform.
Your role is to help students learn programming through personalized guidance using the Socratic method.

TEACHING PRINCIPLES (Socratic Method):
1. Ask guiding questions rather than giving direct answers
2. Help students discover solutions through inquiry and reflection
3. Build on what the student already knows
4. Encourage critical thinking by asking "why" and "how"
5. Break complex problems into smaller, manageable questions
6. Validate student thinking and gently correct misconceptions
7. Only provide direct answers when the student is truly stuck

RESPONSE GUIDELINES:
- Be supportive, patient, and adapt explanations to the student's skill level
- When sharing code examples, ALWAYS use proper markdown code blocks with language specification
- Format code blocks as: ```language\ncode here\n```
- Use inline code formatting with backticks for variable names, functions, etc.
- Keep responses concise and focused (2-4 paragraphs maximum)
- Use analogies and real-world examples to explain abstract concepts
- Celebrate progress and learning moments

Focus on teaching concepts and problem-solving approaches rather than just giving solutions.""",

        PromptType.EXERCISE_GENERATION: """You are an expert programming educator creating personalized coding exercises.
Generate exercises that are appropriate for the student's skill level and interests.
Each exercise should be clear, achievable, and educational.""",

        PromptType.CODE_REVIEW: """You are an experienced software engineer conducting code reviews.
Provide constructive feedback that is educational and actionable.
Focus on code quality, best practices, potential bugs, and learning opportunities.""",

        PromptType.HINT_GENERATION: """You are a helpful coding tutor providing hints without giving away the solution.
Guide the student toward the answer using the Socratic method.
Give progressively more specific hints based on the student's progress.""",

        PromptType.FEEDBACK_GENERATION: """You are an encouraging coding tutor providing feedback on student work.
Highlight both strengths and areas for improvement.
Make feedback specific, actionable, and motivating.""",

        PromptType.ONBOARDING_INTERVIEW: """You are conducting a friendly onboarding interview for a new CodeMentor student.
Ask engaging questions to understand their programming interests, goals, and experience level.
Keep the conversation natural and encouraging.""",

        PromptType.CONCEPT_EXPLANATION: """You are a patient programming tutor explaining technical concepts.
Adapt your explanation to the student's skill level and learning style.
Use examples, analogies, and clear language to make concepts accessible.""",
    }

    # User prompt templates
    TEMPLATES = {
        PromptType.TUTOR_GREETING: """Student profile:
- Name: {student_name}
- Programming language: {language}
- Skill level: {skill_level}
- Career goal: {career_goal}

Greet this student warmly and ask how you can help them today.""",

        PromptType.EXERCISE_GENERATION: """Generate a coding exercise for this student:

Student Profile:
- Programming language: {language}
- Skill level: {skill_level}
- Interests: {interests}
- Recent topics: {recent_topics}
- Difficulty preference: {difficulty}

Exercise Requirements:
- Must be appropriate for {skill_level} level
- Should relate to {interests}
- Must include clear objectives and success criteria
- Estimated completion time: {estimated_time} minutes

Please generate an exercise with:
1. Title
2. Description
3. Learning objectives
4. Requirements/specifications
5. Example input/output (if applicable)
6. Hints (optional)""",

        PromptType.CODE_REVIEW: """Review this code submission:

Repository: {repository_url}
Language: {language}
Files to review: {files}

Student context:
- Skill level: {skill_level}
- Learning goals: {learning_goals}

Code:
{code}

Provide a comprehensive review covering:
1. Code quality and structure
2. Potential bugs or issues
3. Best practices and improvements
4. Security considerations (if applicable)
5. Performance considerations
6. Educational insights""",

        PromptType.HINT_GENERATION: """The student is working on this exercise and needs a hint:

Exercise:
{exercise_description}

Student's current approach:
{student_code}

Student's question:
{student_question}

Context:
- Skill level: {skill_level}
- Previous hints given: {hints_count}

Provide a helpful hint that guides without giving away the complete solution.""",

        PromptType.FEEDBACK_GENERATION: """Provide feedback on this student's work:

Exercise:
{exercise_description}

Student submission:
{student_code}

Evaluation criteria:
{criteria}

Student context:
- Skill level: {skill_level}
- Learning style: {learning_style}

Provide encouraging and constructive feedback that:
1. Acknowledges what they did well
2. Identifies areas for improvement
3. Suggests next steps for learning
4. Motivates continued practice""",

        PromptType.ONBOARDING_INTERVIEW: """You are interviewing a new student. Previous conversation:
{conversation_history}

Current question focus: {current_focus}

Continue the conversation naturally to learn about:
- Programming experience and languages
- Learning goals and career aspirations
- Preferred learning style
- Available time commitment
- Specific interests or project ideas

Ask one engaging question at a time.""",

        PromptType.CONCEPT_EXPLANATION: """Explain this programming concept to the student:

Concept: {concept}
Context: {context}

Student profile:
- Skill level: {skill_level}
- Language: {language}
- Learning style: {learning_style}

Provide a clear explanation that:
1. Introduces the concept at appropriate level
2. Uses relevant examples
3. Explains practical applications
4. Suggests practice exercises (if appropriate)""",
    }

    @classmethod
    def get_system_prompt(cls, prompt_type: PromptType) -> str:
        """
        Get the system prompt for a given prompt type.

        Args:
            prompt_type: The type of prompt

        Returns:
            System prompt string
        """
        return cls.SYSTEM_PROMPTS.get(prompt_type, cls.SYSTEM_PROMPTS[PromptType.TUTOR_GREETING])

    @classmethod
    def render_prompt(cls, prompt_type: PromptType, **kwargs) -> str:
        """
        Render a prompt template with provided parameters.

        Args:
            prompt_type: The type of prompt to render
            **kwargs: Template parameters

        Returns:
            Rendered prompt string

        Raises:
            KeyError: If required template parameters are missing
        """
        template = cls.TEMPLATES.get(prompt_type)
        if not template:
            raise ValueError(f"Unknown prompt type: {prompt_type}")

        try:
            return template.format(**kwargs)
        except KeyError as error:
            raise KeyError(f"Missing required template parameter: {error}")

    @classmethod
    def create_tutor_message(
        cls,
        student_name: str,
        language: str,
        skill_level: str,
        career_goal: str,
    ) -> tuple[str, str]:
        """
        Create a tutor greeting message.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = cls.get_system_prompt(PromptType.TUTOR_GREETING)
        user_prompt = cls.render_prompt(
            PromptType.TUTOR_GREETING,
            student_name=student_name,
            language=language,
            skill_level=skill_level,
            career_goal=career_goal,
        )
        return system_prompt, user_prompt

    @classmethod
    def create_exercise_prompt(
        cls,
        language: str,
        skill_level: str,
        interests: str,
        recent_topics: str = "None",
        difficulty: str = "medium",
        estimated_time: int = 30,
    ) -> tuple[str, str]:
        """
        Create an exercise generation prompt.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = cls.get_system_prompt(PromptType.EXERCISE_GENERATION)
        user_prompt = cls.render_prompt(
            PromptType.EXERCISE_GENERATION,
            language=language,
            skill_level=skill_level,
            interests=interests,
            recent_topics=recent_topics,
            difficulty=difficulty,
            estimated_time=estimated_time,
        )
        return system_prompt, user_prompt

    @classmethod
    def create_code_review_prompt(
        cls,
        repository_url: str,
        language: str,
        files: str,
        code: str,
        skill_level: str,
        learning_goals: str,
    ) -> tuple[str, str]:
        """
        Create a code review prompt.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = cls.get_system_prompt(PromptType.CODE_REVIEW)
        user_prompt = cls.render_prompt(
            PromptType.CODE_REVIEW,
            repository_url=repository_url,
            language=language,
            files=files,
            code=code,
            skill_level=skill_level,
            learning_goals=learning_goals,
        )
        return system_prompt, user_prompt
