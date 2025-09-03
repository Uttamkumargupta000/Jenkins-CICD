# Jenkins Production CI/CD

Fast, safe, and repeatable production releases. This job cuts tags/releases only when real changes exist, waits for GitHub Actions to pass, and updates ArgoCD manifests to deploy—guarded by explicit approvals.

## How It Flows (at a glance)

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant J as Jenkins Pipeline
  participant S1 as Tag & Release Script
  participant GH as GitHub (API)
  participant GA as GitHub Actions
  participant S2 as ArgoCD Updater
  participant AR as argocd-prod (Git)
  participant CD as ArgoCD

  rect rgba(255,245,204,0.95)
    note over J: Build & Tag
    U->>J: Trigger + Select SERVICES + Input Base/Tag
    J->>J: Approval (Build)
    J->>S1: Compare base vs latest tag per repo
    S1->>GH: Create tag + GitHub Release (if changes)
    S1-->>J: JSON of released repos
    loop per released repo
      J->>GH: Query workflow run (production-release.yml, ref=tag)
      GH-->>J: Status (wait until success)
      J->>GA: Await completion
    end
  end

  rect rgba(220,248,198,0.95)
    note over J: Deploy
    J->>J: Approval (Deploy)
    J->>S2: Update image tags for selected services
    S2->>AR: Commit & push to argocd-prod
    AR-->>CD: Git change detected
    CD-->>CD: Sync & deploy to prod
  end
```

## Why it’s impactful

- Reliable: Only releases when diffs exist vs base branch.
- Observable: Blocks until GitHub Actions succeed for the new tag.
- Controlled: Dual approvals for build and production deploy.
- Automated: Updates ArgoCD manifests and pushes in one go.

## Kickstart

- Inputs: Base Branch (e.g., `develop`), Release Tag (e.g., `v1.0.0`), SERVICES list.
- Approvals: Build approval → Deploy approval.
- Result: New GitHub tag/release, successful CI runs, and production updated via ArgoCD.
