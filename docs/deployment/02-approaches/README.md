# 2. Deployment Approaches — Index

This chapter enumerates every deployment option that was seriously
considered, gives each a one-paragraph summary, and links to a detailed
write-up. The detailed write-ups all follow the same template
(architecture diagram, step-by-step setup, auth integration, networking,
IAM, secrets, cost, scaling, operability, pros/cons, when to choose
this), so they can be compared side by side.

The comparison matrix in [`../04-comparison-matrix.md`](../04-comparison-matrix.md)
scores them against the requirements from
[`../01-context.md`](../01-context.md), and
[`../05-recommendation.md`](../05-recommendation.md) picks the winner
for the demo.

| #   | Approach                                  | One-liner                                                                                  | Detailed page                                              |
| --- | ----------------------------------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| A   | Local laptop + secure tunnel              | Keep running on the dev machine, expose via Cloudflare Tunnel / ngrok with auth.           | [`local-tunnel.md`](./local-tunnel.md)                     |
| B   | Streamlit Community Cloud                 | Push to GitHub, click deploy on `share.streamlit.io`.                                      | [`streamlit-community-cloud.md`](./streamlit-community-cloud.md) |
| C   | Third-party PaaS (Render / Fly / HF Spaces) | Container or repo deploy on a generic platform.                                            | [`third-party-paas.md`](./third-party-paas.md)             |
| D   | AWS EC2 single instance                   | One VM in the org's AWS account, Streamlit behind nginx + ALB.                             | [`ec2.md`](./ec2.md)                                       |
| E   | AWS Elastic Beanstalk                     | Managed EC2/ASG/ALB stack for a Python web app, lighter ops than raw EC2.                  | [`elastic-beanstalk.md`](./elastic-beanstalk.md)           |
| F   | AWS App Runner                            | Fully-managed container service, ALB-less, the fastest AWS-native container option.        | [`app-runner.md`](./app-runner.md)                         |
| G   | AWS ECS Fargate behind ALB                | Container on Fargate with ALB + Cognito (Okta) auth, VPC, IAM task role.                   | [`ecs-fargate.md`](./ecs-fargate.md)                       |
| H   | AWS EKS / Kubernetes                      | (Mentioned and rejected for this demo.)                                                    | [`ecs-fargate.md#why-not-eks-for-the-demo`](./ecs-fargate.md#why-not-eks-for-the-demo) |

## 2.1 One-paragraph summaries

### A. Local laptop + secure tunnel
Run `streamlit run app.py` on the laptop exactly like today, then expose
it through a **Cloudflare Tunnel** (free, supports WebSockets, integrates
with Cloudflare Access for Okta SSO and email-based zero-trust). Zero
infra to provision, zero changes to AWS, can be live in under an hour.
The price is that the laptop must stay on, IAM credentials live in
`~/.aws/credentials` on a personal machine, and the demo dies if the
machine sleeps or moves networks. Good for an *hours-to-days* taste
test, not for an org-wide trial. Detail: [`local-tunnel.md`](./local-tunnel.md).

### B. Streamlit Community Cloud
The official free hosting for Streamlit apps. Deploys directly from a
GitHub repo, includes a TLS endpoint at `*.streamlit.app`, supports OAuth
("Streamlit-Authenticator") and Google/GitHub login. The blocker for this
project is **AWS credentials**: Community Cloud has no concept of IAM
roles, so the app would have to authenticate to Bedrock using a
long-lived access key stored in `secrets.toml`. That violates the
security requirement in §1.4.1 and is hard to walk back later. Detail:
[`streamlit-community-cloud.md`](./streamlit-community-cloud.md).

### C. Third-party PaaS (Render / Fly.io / Hugging Face Spaces)
Generic container/PaaS platforms. Render and Fly support persistent
containers and WebSockets, deploy from GitHub, and offer SSO add-ons on
paid plans. Hugging Face Spaces has first-class Streamlit support but is
public by default. All of them share Community Cloud's core problem:
**no IAM-role path to AWS Bedrock**. Detail:
[`third-party-paas.md`](./third-party-paas.md).

### D. AWS EC2 single instance
A single `t3.small` / `t3.medium` Linux VM in the org's AWS account,
running Streamlit behind nginx, fronted by an Application Load Balancer
with an ACM certificate and Cognito + Okta auth. IAM via instance
profile. Maximally simple AWS-native option; everything is touchable and
debuggable. The trade-offs are manual OS patching, manual deploys (or a
hand-rolled `systemd` + `git pull` flow), and the single instance is a
SPOF. Detail: [`ec2.md`](./ec2.md).

### E. AWS Elastic Beanstalk
Beanstalk wraps EC2 + ASG + ALB + CloudWatch into a single "environment"
managed by a `Procfile` or Docker image. Less DIY than raw EC2, more
opinionated than App Runner. WebSockets work via the ALB. Good middle
ground if the team is already familiar with Beanstalk; otherwise it
introduces a third concept layer (Beanstalk-specific config, application
versions, environment tiers) for little gain over App Runner. Detail:
[`elastic-beanstalk.md`](./elastic-beanstalk.md).

### F. AWS App Runner
A fully managed container service: point it at an ECR image or a GitHub
repo, it builds, runs, autoscales, and gives you an HTTPS endpoint with
a managed cert. Supports VPC connectors so it can reach private
resources, supports IAM **instance roles** for AWS API calls, supports
WebSockets (since 2023). The catch for this project: App Runner does
**not** have built-in identity-aware authentication, so SSO must be
added by putting CloudFront + Lambda@Edge or a small auth proxy in
front, *or* by using Streamlit-side auth. Still the lowest-ops AWS
option that meets the security bar. Detail:
[`app-runner.md`](./app-runner.md).

### G. AWS ECS Fargate behind ALB (with Cognito + Okta)
A container running on Fargate inside the org's VPC, fronted by an
Application Load Balancer that performs **Cognito user-pool
authentication federated to Okta (SAML or OIDC)** before forwarding to
the app. IAM via task role. WebSockets and sticky sessions are
first-class on ALB. This is the option that natively satisfies every
requirement in §1.4 — strong identity, IAM roles, private VPC path to
Bedrock, long timeouts, room to scale — at the cost of provisioning
~10 AWS resources (VPC bits, ALB, target group, ECS service, task def,
Cognito pool, IAM roles, log group, ECR repo). Terraform/CDK makes this
a one-shot deploy. Detail: [`ecs-fargate.md`](./ecs-fargate.md).

### H. AWS EKS / Kubernetes
Considered and rejected for the *demo*. EKS is the right answer when you
have a fleet of services, a platform team, and a need for fine-grained
workload isolation. For a single Streamlit container with a ~50-user
audience, it adds a control-plane cost ($73/mo just for the cluster)
and an operational surface (cluster upgrades, node groups, IRSA,
ingress controllers) that buys nothing the simpler options don't
already provide. Brief note in
[`ecs-fargate.md`](./ecs-fargate.md#why-not-eks-for-the-demo).

## 2.2 What was filtered out before getting a page

These were considered briefly and dropped without a full write-up,
because they fail a hard requirement from §1.4:

| Rejected option                          | Hard requirement it fails                                                    |
| ---------------------------------------- | ---------------------------------------------------------------------------- |
| **AWS Lambda + API Gateway**             | Streamlit needs a long-lived process + WebSockets; Lambda has 15 min cap and no native WS support without a separate `$connect/$disconnect` model. |
| **S3 + CloudFront static hosting**       | Streamlit is a Python server, not static assets.                             |
| **AWS Amplify Hosting**                  | Amplify Hosting is for static SPAs / SSR Node — no Python server runtime.    |
| **SageMaker Studio / Notebook hosting**  | Per-user notebook environments, not shared multi-user web apps.              |
| **Vercel / Netlify**                     | Same as Amplify — no Python long-running process / WS support.               |
| **EC2 + public IP, no ALB**              | Forces self-managed TLS, no path to ALB-Cognito-Okta auth; strictly worse than (D). |

## 2.3 How to read the rest of this chapter

Each approach page is structured identically:

1. **TL;DR** — one paragraph + a verdict for this demo.
2. **Architecture** — Mermaid diagram of the runtime topology.
3. **Setup walkthrough** — concrete steps, in order, with the AWS / CLI
   commands or links to the canonical docs.
4. **Authentication integration** — how Okta (or a stop-gap) plugs in.
5. **Networking and security** — VPC posture, egress path, TLS, secrets.
6. **AWS credentials / IAM** — how the app talks to Bedrock.
7. **Cost (rough order of magnitude)** — for the demo workload from
   §1.3.
8. **Scaling characteristics** — what happens at 50 users, at 500.
9. **Operability** — logs, metrics, deploys, rollbacks.
10. **Pros / cons / when to pick this**.

Read whichever approach you are evaluating, then jump to
[`../04-comparison-matrix.md`](../04-comparison-matrix.md) for the
side-by-side and [`../05-recommendation.md`](../05-recommendation.md)
for the decision.
