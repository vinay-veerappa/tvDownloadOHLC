# Ralph Wiggum Skill

The **Ralph Wiggum** technique is a development methodology for AI agents that prioritizes iterative progress over single-shot perfection. It is named after the character Ralph Wiggum from *The Simpsons*, symbolizing a persistent, "I'm helping!" approach that keeps going until the job is done.

## Core Philosophy

- **Iteration > Perfection**: Don't try to get it right the first time. Try, fail, learn, repeat.
- **Failures Are Data**: Every error message is a clue. Use it to refine the approach.
- **Persistence Wins**: The loop stays active until the goal is met or max iterations are reached.
- **Operator Skill Matters**: The quality of the "Completion Promise" and initial prompt determines success.

## When to Use

- **Test-Driven Development (TDD)**: Perfect for getting a suite of tests to pass.
- **Complex Refactoring**: When multiple interdependent changes are needed across files.
- **Fixing Bugs**: Iteratively trying fixes until the bug is verified as gone.
- **Greenfield Projects**: Building a new feature from scratch by starting with a skeleton and iteratively adding meat.

## How to Execute the Ralph Loop

When a user invokes `/ralph-loop` or asks for a Ralph-style iteration:

1. **Define the Goal**: Clearly state what success looks like (the "Completion Promise").
2. **Break it Down**: Identify the first atomic step.
3. **Execute**: Make the change.
4. **Verify**: Run tests, linters, or build commands.
5. **Observe**: If it fails, read the logs. If it succeeds, move to the next step.
6. **Repeat**: Continue until the Completion Promise is fulfilled.

## Best Practices

- **Use `--max-iterations`**: Always have a safety net to prevent infinite loops (default to 5-10).
- **Git Checkpoints**: Commit after every successful iteration to preserve progress.
- **Clear Prompts**: Use specific completion criteria like "All tests pass" or "API responds with 200".
- **Self-Correction**: If you get the same error 3 times, take a step back and research an alternative approach.

## Commands

- `/ralph-loop "<prompt>"`: Start a new iterative loop for the given task.
- `/cancel-ralph`: Stop the current loop.
- `/ralph-status`: View progress and current iteration count.
