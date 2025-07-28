---
applyTo: "ic/test/**/*.ts"
---

### Writing Tests for Canister Functions

When writing tests for canister functions:

- Use Jest for canister testing
- Include setup, execution, and assertion phases in each test
- Test both happy path and error cases
- Use descriptive test names that explain the expected behavior

Example test structure:

```typescript
it("should [expected consequence]", async () => {
  // Setup
  const testData = "world";

  // Execute
  const response = await fetch(`${origin}/db/update`, {
    method: "POST",
    headers: [["Content-Type", "application/json"]],
    body: JSON.stringify({
      hello: testData,
    }),
  });

  const responseJson = await response.json();

  // Assert
  expect(responseJson).toEqual({ hello: "world" });
});
```

After writing the tests, check if the file has any errors:

```bash
npx tsc -p ic/tsconfig.json
```

Then check that they are all passing by executing:

```bash
npm test
```
