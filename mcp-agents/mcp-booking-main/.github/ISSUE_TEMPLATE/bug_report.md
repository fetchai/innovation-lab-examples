---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: 'bug'
assignees: ''
---

## 🐛 Bug Description
A clear and concise description of what the bug is.

## 🔄 To Reproduce
Steps to reproduce the behavior:
1. Call API endpoint '...'
2. With parameters '....'
3. See error

## ✅ Expected Behavior
A clear and concise description of what you expected to happen.

## 🖼️ Screenshots
If applicable, add screenshots to help explain your problem.

## 🌐 Environment
- Node.js version: [e.g. 18.17.0]
- npm version: [e.g. 9.6.7]
- Operating System: [e.g. macOS 13.4]
- MCP Booking version: [e.g. 1.0.0]

## 📋 API Request Details (if applicable)
```json
{
  "searchParams": {
    "location": { "latitude": 25.033, "longitude": 121.5654 },
    "cuisineTypes": ["Italian"],
    "mood": "romantic",
    "event": "dating"
  }
}
```

## 📊 Performance Impact
- [ ] Performance regression
- [ ] Memory leak
- [ ] Increased API calls
- [ ] Timeout issues
- [ ] Other: ___________

## 🔗 Additional Context
Add any other context about the problem here.

## 🧪 Test Case
If possible, provide a minimal test case that reproduces the issue.

```typescript
// Test case code here
```