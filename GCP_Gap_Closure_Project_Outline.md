# Project Outline: GCP Cloud Infrastructure and Delivery Pipeline

Purpose: close the specific gaps identified against the O'Reilly Media System Administrator posting (GCP, Docker/CI-CD, operational SQL on MySQL/PostgreSQL, Ansible/Puppet/Chef, Akamai/WAF concepts) using a project structured the same way as your existing Virtualization and Hybrid Cloud Lab and Network Infrastructure projects, so it can eventually be documented in skills.md and projects.md with real metrics once built.

Since your domain is already on Cloudflare, this version routes DNS, CDN, and WAF through Cloudflare in front of a GCP origin, rather than through Google's native DNS/CDN/Cloud Armor equivalents. This is a genuine improvement, not just a preference: the posting names Cloudflare directly as an acceptable WAF/edge system alongside Akamai, Cloud Armor, and CloudFront, and you already have real, documented Cloudflare DNS proxying and CDN configuration experience from your web development project. Building this way means the Cloudflare piece of the project is first-party experience you can speak to directly, not a substitute you have to explain away.

## Goal

Stand up a small but realistic web application stack on GCP, provisioned entirely through Terraform, deployed through a CI/CD pipeline, backed by a managed SQL database, configured through a configuration management tool, and monitored with the same observability approach you already run in your home lab. The point isn't to build something novel; it's to touch every named gap technology in a single coherent project you can speak to concretely in an interview.

## Phase 1: GCP Foundation and Networking

- Create a GCP project and configure billing alerts/budgets to control free-tier spend.
- Build a VPC with public and private subnets, firewall rules, and Cloud NAT for outbound-only access from private resources.
- Keep DNS on Cloudflare rather than migrating to Cloud DNS, since the domain is already there. Point a subdomain's A/CNAME record at the GCP load balancer or Compute Engine external IP, proxied through Cloudflare (orange-clouded) rather than DNS-only, so Cloudflare sits in front of the GCP origin from day one.
- Issue TLS at both layers: a Cloudflare-managed edge certificate for the public-facing connection, and a Google-managed certificate on the GCP load balancer for the origin connection (Cloudflare Full Strict mode), so the HTTPS/TLS skill covers both edge and origin termination rather than just one hop.
- Set up IAM roles and service accounts on the GCP side following least-privilege, mirroring the RBAC discipline you already apply with Active Directory and Entra ID.
- Provision the GCP-side resources through Terraform from the start, not the console, so the IaC skill directly extends what you already did in AWS. Cloudflare's DNS/proxy records can also be managed through Terraform using Cloudflare's provider, which extends your existing Cloudflare DNS proxying experience into IaC as well.

Closes: GCP fundamentals, VPC/networking, Terraform-on-GCP, Terraform-on-Cloudflare, IAM/RBAC, HTTPS/TLS at both edge and origin, and reinforces your existing Cloudflare DNS/proxy experience rather than replacing it.

## Phase 2: Compute and Containerization

- Containerize a simple application (a basic internal tool, status dashboard, or even a small Flask/Node app) with Docker.
- Push the image to Artifact Registry.
- Deploy it two ways to get breadth: once on Compute Engine (VM-based, closer to traditional sysadmin work) and once on Cloud Run (serverless container, named explicitly in the posting's preferred qualifications).
- Add a Cloud Load Balancer in front of Cloud Run as the GCP-side entry point, but let Cloudflare handle the actual CDN caching at the edge rather than enabling Cloud CDN on top of it. Cloudflare in front of a GCP origin is a realistic, commonly used pattern, and it keeps the CDN layer on the platform you already operate.

Closes: Docker, GCP Compute Engine, Cloud Run, CDN (via your existing Cloudflare configuration rather than a new tool).

## Phase 3: CI/CD Pipeline

- Connect a GitHub repository to Cloud Build.
- Build a pipeline that triggers on push: lint/test the app, build the Docker image, push to Artifact Registry, and deploy to Cloud Run automatically.
- Add a manual approval gate before production deploy, to mirror real-world change control rather than a fully open pipeline.

Closes: Cloud Build, CI/CD pipeline experience, container/CI-CD stack named directly in the posting.

## Phase 4: Database Layer

- Provision Cloud SQL for PostgreSQL (or MySQL) through Terraform.
- Configure private IP connectivity so the database is not exposed to the public internet, automated backups, and a read replica if budget allows.
- Connect the containerized app to the database and perform basic operational tasks yourself: user/role management, backup verification, restore test, and a basic performance check (slow query log or equivalent).

Closes: the exact MySQL/PostgreSQL gap named in the posting, at an operational level rather than just "provisioned and walked away."

## Phase 5: Configuration Management

- Pick one tool, Ansible is the most natural fit given your existing Linux/Proxmox environment, and use it to configure the Compute Engine VM from Phase 2: package installation, user accounts, hardening baseline, and application deployment as code rather than manual SSH steps.
- Optionally extend Ansible to also manage configuration on one or two VMs in your existing Proxmox lab, which ties this new project back into your existing documented infrastructure instead of leaving it as an isolated cloud sandbox.

Closes: Ansible/Puppet/Chef gap.

## Phase 6: Monitoring, Security, and AI-Assisted Operations

- Stand up Cloud Monitoring and Cloud Logging on the GCP resources, or continue your existing Grafana/Loki pattern by shipping GCP logs into your home lab's observability stack for a single-pane-of-glass view.
- Configure Cloudflare's WAF directly on the proxied domain: enable the managed ruleset, add at least one custom rule (rate limiting on a login or API path, or a geographic restriction), and turn on Cloudflare's DDoS protection. This is the strongest substitution in the whole project, since the posting names Cloudflare itself as an acceptable WAF/edge system alongside Akamai, so this closes that gap with real first-party Cloudflare usage rather than an adjacent tool you'd have to explain.
- Optionally also enable Cloud Armor on the GCP load balancer as a second, origin-side layer, so you can speak to both an edge WAF (Cloudflare) and a cloud-native WAF (Cloud Armor) if asked to compare them.
- Use an AI-assisted workflow (Claude, ChatGPT, or Copilot, consistent with what you already do at the Medical Board of California) to triage a sample set of Cloudflare and Cloud Logging entries: have it flag anomalies or errors, then validate its output manually before acting on it. Document this as a deliberate human-in-the-loop process, not blind automation.

Closes: monitoring/observability on GCP, Cloudflare WAF (a named-tool match, not a substitute), Cloud Armor as a secondary comparison point, AI-assisted log analysis at an operational level.

## Phase 7: Documentation and Metrics

- Write the same kind of structured runbook you already produce professionally: architecture diagram, Terraform module breakdown, deployment steps, rollback procedure, and incident response notes for at least one simulated failure (database failover, bad deploy caught by the approval gate, etc.).
- Capture real numbers as you go, the same way projects.md already does for your other projects: deploy time before/after CI/CD automation, database restore time, cost per month at idle, time saved by Ansible-driven config versus manual setup. These become the metrics for a future XYZ-format resume bullet once the project is real and complete.

## Suggested Sequencing

Phases 1 through 4 form the minimum viable version of this project and already close the largest named gaps (GCP, Docker, CI/CD, SQL), with Cloudflare sitting in front of the GCP origin from the start rather than bolted on later. Phases 5 through 7 round it out for Ansible, the Cloudflare WAF configuration, and AI-assisted operations, and can be added incrementally rather than all at once.

## Honest Framing for Future Interviews

Once built, this project should be described the same way your existing home lab projects are: a genuine, hands-on personal project, not professional production experience. The value in an interview is being able to speak concretely and specifically about GCP services, Terraform-on-GCP, a real CI/CD pipeline, and operational PostgreSQL/MySQL work, rather than only being able to discuss these technologies abstractly. It does not convert into "years of GCP experience" and should not be framed as such; it converts a hard "no experience" answer into a credible "here's exactly what I've built and how it works" answer.

The Cloudflare layer is the one piece of this project that isn't a gap-closing exercise at all, it's an extension of real, already-documented experience (Cloudflare DNS proxying and CDN configuration from your web development project) into a more advanced architecture. That distinction is worth making explicitly in an interview: most of this project demonstrates new learning, but the Cloudflare/WAF piece demonstrates depth on something you already do.
