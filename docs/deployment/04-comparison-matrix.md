# 4. Comparison Matrix

Each approach scored 1 (worst) — 5 (best) against the decision drivers
from [`01-context.md` §1.5](./01-context.md#15-decision-drivers-ranked).
Weights reflect the ranked ordering of those drivers.

## 4.1 Scoring

| Driver                                  | Weight | (A) Local + tunnel | (B) Streamlit Cloud | (C) PaaS | (D) EC2 | (E) Beanstalk | (F) App Runner | (G) Fargate + ALB |
| --------------------------------------- | :----: | :----------------: | :-----------------: | :------: | :-----: | :-----------: | :------------: | :---------------: |
| Security posture (IAM role, VPC, non-public) | ×5 | 2                  | 1                   | 1        | 5       | 5             | 5              | 5                 |
| Future-fit (Opus, agentic, Okta)        |  ×4   | 1                  | 1                   | 2        | 4       | 4             | 4              | 5                 |
| Time to first user                      |  ×3   | 5                  | 5                   | 4        | 3       | 3             | 4              | 2                 |
| Operational simplicity                  |  ×2   | 5                  | 5                   | 4        | 2       | 3             | 4              | 3                 |
| Cost at demo scale                      |  ×1   | 5                  | 5                   | 5        | 4       | 4             | 4              | 3                 |
| **Weighted total (max = 75)**           |        | **44**             | **39**              | **38**   | **58**  | **60**        | **65**         | **60**            |

Weights sum to 15, so the theoretical maximum is 15 × 5 = 75.

Reading: **(F) App Runner** wins outright, **(E) Beanstalk** and
**(G) ECS Fargate + ALB** tie for second. (D) EC2 is close behind. The
cheap-and-cheerful options (A, B, C) score well on speed and cost but
lose decisively on the weighted security and future-fit columns.

Note that (E) and (G) tying is a quirk of equal weights and rounded
scores — (G) is the better *architecture* (native ALB-Cognito-Okta,
production-shape), while (E) buys ease via Beanstalk's wrappers. The
recommendation in [`05-recommendation.md`](./05-recommendation.md)
breaks the tie in favor of (G) for the production trajectory while
picking (F) for the demo itself.

## 4.2 Side-by-side feature matrix

| Capability                                    | (A) | (B) | (C) | (D) | (E) | (F) | (G) |
| --------------------------------------------- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| Native WebSocket support                      |  ✓  |  ✓  |  ✓  |  ✓  |  ✓  |  ✓  |  ✓  |
| Long request timeouts (> 120 s)               |  ✓  |  ✓  |  ✓  |  ✓  |  ✓  | 120 s/req |  ✓ (configurable) |
| IAM role for AWS auth (no static key)         |  ✓¹ |  ✗  |  ✗  |  ✓  |  ✓  |  ✓  |  ✓  |
| Private VPC path to Bedrock                   |  ✗  |  ✗  |  ✗  |  ✓  |  ✓  |  ✓ (via VPC connector) |  ✓ |
| Non-public ingress                            |  ✓ via CF |  ✗ |  ✓ paid |  ✓ via ALB |  ✓ |  ✓ private ingress |  ✓ |
| ALB-Cognito-Okta SAML native                  |  —  |  —  |  —  |  ✓  |  ✓  |  ✗ (need CF or CF+L@E) |  ✓ |
| Sticky sessions                               |  ✓ (single replica) |  ✓ (single) |  ✓ (single) |  ✓ |  ✓ |  ✗ (single replica) |  ✓ |
| Horizontal autoscaling                        |  ✗  |  ✗  |  paid |  ✗ |  ✓ |  ✓ (no sticky) |  ✓ |
| Zero-downtime deploys                         |  ✗  |  ~  |  ~  |  ✗ |  ✓ |  ✓ |  ✓ |
| AWS-native logs / metrics                     |  ✗  |  ✗  |  ✗  |  ✓ |  ✓ |  ✓ |  ✓ |
| Reproducible IaC (Terraform/CDK)              |  partial |  ✗  |  partial |  ✓ |  ✓ |  ✓ |  ✓ |
| Production-shape ≡ demo-shape                 |  ✗  |  ✗  |  ✗  |  partial |  partial |  ✓ |  ✓ |

¹ Local SSO session token, not a workload identity. Better than a
static key, worse than a workload-attached role.

## 4.3 Cost summary (hosting only; Bedrock excluded)

| Approach                  | Approx. monthly hosting |
| ------------------------- | ----------------------- |
| (A) Local + tunnel        | $0                      |
| (B) Streamlit Cloud       | $0                      |
| (C) PaaS                  | $5–$25                  |
| (D) EC2 + ALB             | ~$70                    |
| (E) Beanstalk             | ~$70–$75                |
| (F) App Runner            | ~$40 (with VPC endpoints) |
| (G) Fargate + ALB         | ~$100                   |

All approaches share the same Bedrock per-token bill — that is by far
the dominant cost in operation, and is independent of where the app
runs.

## 4.4 Time-to-first-user estimate (effort, not calendar)

| Approach                  | Engineer-hours to first authenticated URL |
| ------------------------- | ---------------------------------------- |
| (A) Local + tunnel        | 1–2 h                                    |
| (B) Streamlit Cloud       | 1–2 h (most of it is the IAM-user dance) |
| (C) PaaS                  | 2–4 h                                    |
| (D) EC2 + ALB             | 1–2 d (Terraform from scratch)           |
| (E) Beanstalk             | 1 d                                      |
| (F) App Runner            | 0.5–1 d (with Cloudflare Access auth)    |
| (G) Fargate + ALB         | 2–3 d (Terraform from scratch)           |

If pre-existing org Terraform modules are available, (D)/(E)/(G) drop
by ~half.

## 4.5 Risk register

| Risk                                                     | Affects        | Mitigation                                            |
| -------------------------------------------------------- | -------------- | ----------------------------------------------------- |
| Static AWS key leak via Streamlit Secrets / PaaS         | (B), (C)       | Scope IAM tightly; rotate weekly; prefer (F)/(G)      |
| Laptop sleep / network change kills demo                 | (A)            | Recommend as stop-gap only                            |
| WebSocket / sticky-session misconfig under multi-replica | (D), (E), (G)  | Single replica until session externalization          |
| Long agentic flow exceeds 120 s App Runner per-req cap   | (F)            | Stream over WS (Streamlit does this); test early      |
| Cloudflare TLS termination policy violation              | (A), (C), (F+CF) | Check org policy; otherwise pick CF+Lambda@Edge or ALB |
| Bedrock cost runaway during open testing                 | all            | AWS Budgets + per-user prompt cap + KB query cap      |
| Streamlit session state lost on task replace             | (F), (G)       | Externalize to Redis post-demo                        |
| Okta admin time not available                            | all            | Cloudflare Access OTP as stop-gap; switch later       |
