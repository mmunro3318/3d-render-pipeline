# Testing Guidelines

Best practices for writing tests in this codebase. Born from a red team audit that found 44% of our tests were providing zero real protection.

**Seed expert security and testing agents to write and review tests and the code that passes those tests. Do not skip review.**

## The One-Question Test

Before committing any test, ask: **"If I deleted the function this test covers, would the test fail?"**

- **YES** → the test has value. Ship it.
- **NO** → the test is theater. It's testing a mock or a copy, not your code. Fix it or delete it.

## Three Patterns (Good, Bad, Ugly)

### Good: Import the real function

```js
import { sanitizeCell } from '@/lib/utils/csv';

it('prefixes = with single quote', () => {
  expect(sanitizeCell('=SUM(A1)')).toBe("'=SUM(A1)");
});
```

Why it works: `sanitizeCell` is the real function. Delete it from csv.js → test fails with import error. Change its logic → test catches the regression.

### Bad: Copy the function into the test

```js
// DON'T DO THIS
function sanitizeCell(value) { /* copied from csv.js */ }

it('prefixes = with single quote', () => {
  expect(sanitizeCell('=SUM(A1)')).toBe("'=SUM(A1)");
});
```

Why it fails: This tests the copy, not the real code. If someone changes csv.js, this test still passes against the stale copy.

### Ugly: Test the mock, not the code

```js
// DON'T DO THIS
const mock = buildMockSupabase({ role: 'admin' });
const profile = await mock.from('profiles').select('role').eq('id', '123').single();
expect(['admin', 'dev'].includes(profile.data.role)).toBe(true);
```

Why it fails: You told the mock to return `'admin'`, then asked "did you return admin?" The real `requireAdmin()` function is never called.

## How to Test Server Actions

Server Actions use `'use server'` and can't be imported normally. Use dynamic import:

```js
vi.mock('@/lib/supabase/server', () => ({ createClient: vi.fn() }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

it('rejects unauthenticated user', async () => {
  const mock = buildMockSupabase({ userId: null });
  createClient.mockResolvedValue(mock);

  const { createPayer } = await import('@/lib/actions/mutations.js');
  const result = await createPayer({ name: 'Test' });
  expect(result).toEqual({ success: false, error: expect.stringContaining('Not authenticated') });
});
```

This calls the **real** `createPayer`, which internally calls `requireAdmin()`, which hits our mocked Supabase. We mock the database layer, not the business logic.

## When to Extract vs. Test Through the API

| Situation | Approach |
|-----------|----------|
| Pure helper function (no DB, no framework) | Extract to `lib/utils/`, import directly |
| Logic inside a Server Action | Test through the exported action via dynamic import |
| React component logic | Extract pure logic to `lib/utils/`, test the util directly |
| Constants shared between source and test | Extract to `lib/constants/`, import in both |

Shared utility modules in this project:
- `lib/utils/validation.js` — validateRequired, validatePositiveAmount, mapPostgrestError, validateAllocations
- `lib/utils/report-helpers.js` — groupAgingByPayer, computeCollectionRate, computeDSO, generateInvoiceNumber
- `lib/utils/allocations.js` — buildAllocations
- `lib/utils/csv.js` — sanitizeCell, formatCSV

## Edge Cases Worth Testing

Financial apps need extra paranoia. Always test:

- **Float precision**: `0.1 + 0.2 !== 0.3` in JavaScript. Test amounts like `$0.10 + $0.20`.
- **Boundary values**: What happens at exactly the threshold? (e.g., allocation total equals amount received)
- **Null/undefined inputs**: What does the function do with missing data?
- **Substring collisions**: If you match on `detail.includes('name')`, does `'invoice_name'` match too?
- **Overflow**: What happens at sequence 999 → 1000 if you're zero-padding to 3 digits?

## Mutation Testing

Run `npm run test:mutate` to check if your tests actually catch bugs. StrykerJS changes your code (flips operators, deletes lines) and sees if tests still pass. If they do, the test isn't catching what you think.

Current baseline: **86.54%** on `lib/utils/`. Target: stay above 80%.

## Test Commands

```bash
npm test              # Run all 184 tests (~3s)
npm run test:watch    # Watch mode for development
npm run test:mutate   # Mutation testing (~3 min)
```