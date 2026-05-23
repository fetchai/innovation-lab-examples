# Profile README — automatic contributor badge

When your PR is **merged** into `fetchai/innovation-lab-examples`, the [**Award Contributor Badge**](../../../.github/workflows/award-contributor-badge.yml) workflow:

1. Adds the badge to your agent README under `contributors/<your-agent>/`
2. Registers you in [`BADGE_REGISTRY.json`](../BADGE_REGISTRY.json)
3. Comments on your PR with copy-paste markdown

## Fully automatic profile README (one-time setup)

Your GitHub Profile README lives in a repo named **`YOUR_USERNAME/YOUR_USERNAME`**.

1. Open (or create) https://github.com/YOUR_USERNAME/YOUR_USERNAME
2. Add a workflow file — copy [`profile-readme-badge.yml`](./profile-readme-badge.yml) to:

   ```text
   YOUR_USERNAME/YOUR_USERNAME/.github/workflows/innovation-lab-badge.yml
   ```

3. After your Innovation Lab PR is merged, either:
   - Go to **Actions → Sync Innovation Lab Contributor Badge → Run workflow**, or
   - Wait for the weekly schedule (Mondays 12:00 UTC)

The workflow reads the public registry and inserts the badge if your username is listed.

## Manual paste

Add this line to the top of your profile `README.md`:

```markdown
[![Innovation Lab Contributor](https://img.shields.io/badge/Innovation_Lab-Contributor-3D8BD3?style=for-the-badge&logo=github)](https://github.com/fetchai/innovation-lab-examples/tree/main/contributors)
```

Or use the image badge:

```markdown
![Innovation Lab Contributor](https://raw.githubusercontent.com/fetchai/innovation-lab-examples/main/.github/badges/contributor.png)
```

## Available badge images

| Badge | File |
|-------|------|
| Contributor (default on merge) | [`.github/badges/contributor.png`](../../.github/badges/contributor.png) |
| Participant | `participant.png` |
| Expert Coder | `expert-coder.png` |
| AI Master | `ai-master.png` |

Maintainers may award additional badges in follow-up PRs.
