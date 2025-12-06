# TypeScript Client Generation Guide

This document explains how to generate a TypeScript client library from the CodeMentor API OpenAPI specification.

## Prerequisites

- Node.js 14+ installed
- Access to the running CodeMentor backend (or the OpenAPI spec file)

## Option 1: Using openapi-typescript-codegen

### Installation

```bash
npm install --save-dev openapi-typescript-codegen
# or
yarn add --dev openapi-typescript-codegen
```

### Generate Client

```bash
# From running server
npx openapi-typescript-codegen \
  --input http://localhost:5000/openapi.json \
  --output ./src/api/generated \
  --client axios

# From file
npx openapi-typescript-codegen \
  --input ./openapi.json \
  --output ./src/api/generated \
  --client axios
```

### Usage Example

```typescript
import { AuthService, ExerciseService } from './api/generated';

// Login
const loginResponse = await AuthService.postAuthLogin({
  email: 'user@example.com',
  password: 'secure_password'
});

// Get daily exercise
const exercise = await ExerciseService.getExercisesDaily();
```

## Option 2: Using @openapitools/openapi-generator-cli

### Installation

```bash
npm install --save-dev @openapitools/openapi-generator-cli
```

### Generate Client

```bash
npx openapi-generator-cli generate \
  -i http://localhost:5000/openapi.json \
  -g typescript-axios \
  -o ./src/api/generated
```

### Configuration File

Create `openapitools.json`:

```json
{
  "generator-cli": {
    "version": "7.1.0",
    "generators": {
      "typescript": {
        "generatorName": "typescript-axios",
        "output": "./src/api/generated",
        "inputSpec": "http://localhost:5000/openapi.json",
        "additionalProperties": {
          "npmName": "@codementor/api-client",
          "npmVersion": "0.1.0",
          "supportsES6": true,
          "withInterfaces": true
        }
      }
    }
  }
}
```

Then run:

```bash
npx openapi-generator-cli generate -c openapitools.json
```

## Option 3: Using openapi-typescript (Type Definitions Only)

For type-safe API calls without generated code:

### Installation

```bash
npm install --save-dev openapi-typescript
```

### Generate Types

```bash
npx openapi-typescript http://localhost:5000/openapi.json \
  --output ./src/api/schema.d.ts
```

### Usage with Axios

```typescript
import type { paths } from './api/schema';
import axios from 'axios';

type LoginRequest = paths['/api/auth/login']['post']['requestBody']['content']['application/json'];
type LoginResponse = paths['/api/auth/login']['post']['responses']['200']['content']['application/json'];

const loginData: LoginRequest = {
  email: 'user@example.com',
  password: 'secure_password'
};

const response = await axios.post<LoginResponse>('/api/auth/login', loginData);
```

## Recommended Approach

For the CodeMentor frontend, we recommend **openapi-typescript-codegen** with axios because:

1. Generates clean, readable TypeScript code
2. Integrates seamlessly with existing Axios setup
3. Provides type-safe API calls with minimal boilerplate
4. Supports cookies (withCredentials) for our authentication

## Integration with Frontend

### 1. Generate Client

Add to `package.json`:

```json
{
  "scripts": {
    "generate:api": "openapi-typescript-codegen --input http://localhost:5000/openapi.json --output ./src/api/generated --client axios",
    "generate:api:file": "openapi-typescript-codegen --input ../backend/openapi.json --output ./src/api/generated --client axios"
  }
}
```

### 2. Configure Client

Create `src/api/client.ts`:

```typescript
import { OpenAPI } from './generated';

// Configure base URL
OpenAPI.BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

// Enable credentials for cookie-based auth
OpenAPI.WITH_CREDENTIALS = true;

// Add CSRF token to requests
OpenAPI.HEADERS = async () => {
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrf_token='))
    ?.split('=')[1];

  return {
    'X-CSRF-Token': csrfToken || ''
  };
};

export { OpenAPI };
```

### 3. Use Generated Services

Replace manual API calls with generated services:

```typescript
// Before
const response = await apiClient.post('/api/auth/login', { email, password });

// After
import { AuthService } from './api/generated';
const response = await AuthService.postAuthLogin({ email, password });
```

## Keeping Client Updated

### Manual Update

```bash
npm run generate:api
```

### Automatic Update (CI/CD)

Add to GitHub Actions workflow:

```yaml
- name: Generate API Client
  run: |
    npm run generate:api
    git diff --exit-code src/api/generated || echo "API client needs updating"
```

## Troubleshooting

### CORS Errors

Ensure backend CORS allows the frontend origin:

```python
# backend/src/config.py
CORS_ORIGINS = ["http://localhost:3000"]
```

### Type Errors

If encountering type errors, regenerate the client:

```bash
rm -rf src/api/generated
npm run generate:api
```

### Authentication Issues

Ensure `withCredentials: true` is set:

```typescript
OpenAPI.WITH_CREDENTIALS = true;
```

## Further Reading

- [OpenAPI TypeScript Codegen](https://github.com/ferdikoomen/openapi-typescript-codegen)
- [OpenAPI Generator](https://openapi-generator.tech/)
- [openapi-typescript](https://github.com/drwpow/openapi-typescript)
