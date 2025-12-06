<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md

You are an expert. Experts always look at the documentation before they try to use a library.
We are on a Macbook Pro m3 with 64 gb of memory, though you probably want to check available RAM before running memory intensive experiments.

## Project Overview

LLM Coding Tutor Platform (working name: "CodeMentor") - An adaptive web-based learning system that leverages large language models to provide personalized coding education through daily exercises, adaptive difficulty, community learning, and mentorship.

## Project Structure

```
llm_tutor/
├── plans/                  # Project planning documentation
│   ├── requirements.md     # Comprehensive feature requirements (v1.1)
│   ├── roadmap.md          # Phased parallel execution roadmap (v1.1)
│   └── priorities.md       # Business analysis and prioritization (v1.0)
└── .mcp.json              # MCP server configuration
```



The system provides three persistent channels for agent coordination:

1. **roadmap** - Discussion about project roadmap and planning
2. **parallel-work** - Coordination for parallel work among agents
3. **errors** - Error reporting and troubleshooting

### MCP Tools for Agent Communication

The chat system exposes these tools via MCP:

- `set_handle` - Set your agent handle/username (e.g., 'backend-engineer', 'project-manager')
- `get_my_handle` - Retrieve your current handle
- `list_channels` - List all available chat channels
- `send_message` - Send a message to a channel
- `read_messages` - Read recent messages from a channel (default: last 50)

## Development Workflow

### Parallel Development Strategy

This project is designed for **maximum parallelization** with multiple agents/teams working concurrently. The roadmap identifies independent work streams that can execute simultaneously.

**Key Principles**:
1. Use NATS chat channels to coordinate parallel work
2. Set your agent handle before starting work
3. Post to `parallel-work` channel when beginning a work stream
4. Check for blocking dependencies before starting
5. Post to `errors` channel if encountering blockers



Prefer raw SQL over SQLAlchemy except for model definition.

Always implement a centralized, robust logging module for each component of the project
Always use python if possible
Never use single-letter variable names
Use Playwright to check your work if creating a web-based project, always take a screenshot in between actions so you can be sure that the routes exist.

Every project should have a requirements.md file, and it should be in the /plans directory
Always make a plan, and save requirements and plans in the /plans directory. The main execution plan should be in plan.md
**Save markdown-formatted diary entries in /devlog**, under the feature name. Always check in plans and diary entries.


NEVER comment out existing features or functionality to "simplify for now" or "focus on testing." Instead:
- Create separate test files or scripts for isolated testing
- Use feature flags or configuration switches if you need to temporarily disable functionality
- Maintain all existing features while adding new ones
- If testing specific behavior, write a dedicated test harness that doesn't modify the main codebase


When writing tests, prioritize integration testing over heavily mocked unit tests:
- Test real interactions between components rather than isolated units with mocks
- Only mock external dependencies (APIs, databases) when absolutely necessary
- Test the actual integration points where bugs commonly occur
- If you must mock, mock at the boundaries (external services) not internal components
- Write tests that exercise the same code paths users will actually use

Remember: The goal is to catch real bugs that affect users, not to achieve artificial test coverage metrics.

Always use a virtual environment, either create one if it isn't present, or remember to activate it, it's probably in ./env or ./venv

Check the web for the documentation for how SDKs actually work instead of trying to directly recall everything. Always check the docs before you use a library.

Move modules between files with sed and awk when doing a refactor so you don't have to output the whole file yourself, but verify the line numbers are correct before doing the command.

Don't confirm once you find a solution- just proceed to fix it. 
Your role is not to teach but to execute. 
Plan as nessecary but always proceed to write code or terminal commands in order to execute. The user will click decline if they don't agree with the next step in the plan.
Always background processes that don't immediately exit, like web servers.

Never use Conda, ever, under any circumstances.

Don't hallucinate.
Don't summarize what was done at the end, just pause and wait for the user to review the code, then they'll tell you when to commit.