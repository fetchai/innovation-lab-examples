# Branch Protection Setup (Maintainers)

Community PRs must **not merge without review**. Configure these settings on the `main` branch in GitHub:

**Settings → Branches → Branch protection rules → `main`**

## Required settings

1. **Require a pull request before merging**
   - Require approvals: **1** (or more)
   - Dismiss stale pull request approvals when new commits are pushed: recommended

2. **Require review from Code Owners** (optional but recommended)
   - Uses [.github/CODEOWNERS](./CODEOWNERS) (`@fetchai`)

3. **Require status checks to pass before merging**
   - Require branches to be up to date before merging: recommended
   - Required checks (must match actual workflow job names — a required check that
     no workflow produces blocks every PR indefinitely):

     From `pull_request_ci.yml`:
     - `stargazer-gate`
     - `changelog-check`
     - `lint`
     - `format`
     - `typecheck`
     - `validate-architecture`
     - `test`

     From `review-required.yml`:
     - `review-required`

4. **Do not allow bypassing the above settings** (recommended for `main`)

5. **Restrict who can push to matching branches** (optional)
   - Prevents direct pushes to `main`

## CI vs GitHub settings

- The `review-required` workflow job fails until a reviewer approves the PR. It lives in its own
  workflow so that it also runs on `pull_request_review` events — otherwise the check would stay
  red after an approval and never re-evaluate.
- Branch protection must list `review-required` as a required check, or merges can still proceed if only other checks are required.
- Admins can bypass protection unless "Include administrators" is enforced.

## After updating workflows

When jobs are added, removed or renamed in any PR workflow, re-open branch protection and update
the required check list to match. Required checks are matched by job name; a stale name that no
workflow produces will never report and will block merges forever.
