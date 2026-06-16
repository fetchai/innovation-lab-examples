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
   - Required checks (match workflow job names in `pull_request_ci.yml`):
     - `stargazer-gate`
     - `contributor-path-check`
     - `changelog-check`
     - `review-required`
     - `lint`
     - `format`
     - `typecheck`
     - `validate-architecture`
     - `test`

4. **Do not allow bypassing the above settings** (recommended for `main`)

5. **Restrict who can push to matching branches** (optional)
   - Prevents direct pushes to `main`

## CI vs GitHub settings

- The `review-required` workflow job fails until a reviewer approves the PR.
- Branch protection must list `review-required` as a required check, or merges can still proceed if only other checks are required.
- Admins can bypass protection unless "Include administrators" is enforced.

## After updating workflows

When new jobs are added to `pull_request_ci.yml`, re-open branch protection and add the new check names to the required list.
