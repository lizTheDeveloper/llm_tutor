#!/usr/bin/env python3
"""
Script to fix test_progress.py authentication mocking pattern.
Replaces inline patch() calls with mock_jwt_auth_factory fixture.
"""
import re

def fix_test_function(content):
    """Fix a single test function's auth pattern."""
    # Pattern to match the old auth mocking
    old_pattern = r"    with patch\('src\.middleware\.auth_middleware\.verify_jwt_token', return_value=\{'user_id': test_user_with_progress\.id\}\):\n        response = await client\.(get|post|put|patch|delete)\("

    # New pattern - no with statement, just call the client directly
    def replacement(match):
        http_method = match.group(1)
        return f"    with mock_jwt_auth_factory(test_user_with_progress):\n        response = await client.{http_method}("

    content = re.sub(old_pattern, replacement, content)

    # Also need to add mock_jwt_auth_factory to function signatures that use it
    # Find functions that have the old patch pattern
    def add_fixture_to_signature(match):
        func_line = match.group(0)
        # Check if mock_jwt_auth_factory is already in the signature
        if 'mock_jwt_auth_factory' in func_line:
            return func_line
        # Add it before patched_get_session
        if 'patched_get_session' in func_line:
            return func_line.replace('patched_get_session', 'mock_jwt_auth_factory, patched_get_session')
        # Otherwise add it at the end before the closing paren
        return func_line.replace('):', ', mock_jwt_auth_factory):')

    # Match test function signatures that need the fixture
    func_pattern = r'^async def test_[^(]+\([^)]+\):'

    lines = content.split('\n')
    result_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this is a test function signature
        if re.match(r'^async def test_', line):
            # Look ahead to see if this function uses auth mocking
            func_content = []
            j = i
            while j < len(lines) and (j == i or not re.match(r'^(async def |@pytest)', lines[j])):
                func_content.append(lines[j])
                j += 1
            func_text = '\n'.join(func_content)

            # If it uses the old auth pattern and doesn't have factory yet
            if "patch('src.middleware.auth_middleware.verify_jwt_token'" in func_text:
                if 'mock_jwt_auth_factory' not in line:
                    # Add the fixture to the signature
                    if 'patched_get_session' in line:
                        line = line.replace('patched_get_session', 'mock_jwt_auth_factory, patched_get_session')
                    else:
                        line = line.replace('):', ', mock_jwt_auth_factory):')

        result_lines.append(line)
        i += 1

    content = '\n'.join(result_lines)

    return content

def main():
    # Read the file
    with open('tests/test_progress.py', 'r') as f:
        content = f.read()

    # Apply fixes
    content = fix_test_function(content)

    # Write back
    with open('tests/test_progress.py', 'w') as f:
        f.write(content)

    print("Fixed test_progress.py")

if __name__ == '__main__':
    main()
