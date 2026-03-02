---
paths:
  - "src/**/*client*"
  - "src/**/*crawl*"
  - "src/**/*fetch*"
  - "scripts/*crawl*"
  - "scripts/*fetch*"
---

# API Client and Data Fetching Rules

- Implement rate limiting between requests (minimum 1 second delay)
- Use exponential backoff for retries on failure (max 3 retries)
- Handle HTTP errors gracefully: log the error and continue, do not crash
- Store raw JSON responses before parsing (raw -> processed pipeline)
- Make fetching idempotent: re-running should not create duplicate data
- Use sessions (httpx.Client) for connection pooling
- Set reasonable timeouts on all HTTP requests (30 seconds default)
- Log the URL being fetched and the response status code
- NEVER log or store authentication headers or tokens
