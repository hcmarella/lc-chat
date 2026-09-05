# BizChat — LangGraph analyst on a business dashboard

A chat interface welded to a live BI dashboard. The agent answers business
questions by calling warehouse tools, never from memory, and the dashboard
re-renders from whatever the agent just queried.

```
web (nginx SPA)  ──►  backend (FastAPI + LangGraph)  ──►  warehouse tools
        ▲                        │
        └── SSE token stream ◄───┘
```

## Layout

| Path | What it is |
|---|---|
| `backend/app/graph/agent.py` | LangGraph `StateGraph`: agent ⇄ ToolNode loop, SQLite checkpointer per thread |
| `backend/app/graph/tools.py` | Business tools (`get_metric`, `compare_segments`, `run_sql` with a read-only guard) |
| `backend/app/api/routes.py` | `/chat`, `/chat/stream` (SSE), `/dashboard/summary`, health probes |
| `web/` | Dependency-free SPA: KPI tiles, sparklines, SVG trend chart, streaming chat |
| `deploy/docker/` | Backend + web images, nginx reverse proxy (SSE buffering off) |
| `deploy/k8s/` | Deployments, HPA, and **two** ingress options |
| `deploy/terraform/` | VPC, EKS, ECR, Secrets Manager, optional API Gateway module |

## Run locally

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build
```

Then open http://localhost:8080.

## The gateway decision

`deploy/terraform/variables.tf` has one switch, `enable_api_gateway`.

**`true` — API Gateway HTTP API + VPC Link → internal ALB.** You get JWT
authorization, per-route throttling, WAF, usage plans and access logs before
traffic reaches the cluster. The gateway injects the verified `sub` as
`x-principal-id`, and the app scopes LangGraph threads to it
(`BIZCHAT_BEHIND_API_GATEWAY=true`).

*Caveat worth knowing before you pick this:* API Gateway HTTP APIs buffer
responses and cap integrations at 30 seconds. Long streaming turns will be
delivered in one chunk or cut off. If token-by-token streaming matters, either
keep `/api/v1/chat/stream` off the gateway, or run the non-streaming `/chat`
route behind it.

**`false` — internet-facing ALB straight to the services.** One fewer hop,
true SSE streaming, lower cost. Auth then belongs in the app (OIDC middleware)
and rate limiting in the ALB/WAF.

Both paths deploy the same images; only the ingress manifest differs
(`ingress.yaml` vs `ingress-vpclink.yaml`).

## Deploy to EKS

```bash
cd deploy/terraform && terraform init && terraform apply -var enable_api_gateway=true
```

```bash
aws eks update-kubeconfig --region us-east-1 --name bizchat
```

Build and push both images to the ECR repos Terraform created, replace
`ACCOUNT`/`REGION` in `deploy/k8s/*.yaml`, then:

```bash
kubectl apply -f deploy/k8s/
```

With the gateway enabled, apply `ingress-vpclink.yaml` first, read the internal
ALB listener ARN, and re-apply Terraform with `internal_alb_listener_arn` set.

## Wiring your own data

`tools.py` returns sample series. Point `get_metric`/`compare_segments` at your
warehouse client and set `BIZCHAT_WAREHOUSE_DSN`; the graph, API and UI need no
changes. Swap `SqliteSaver` for the Postgres checkpointer once you run more than
one replica — SQLite on an `emptyDir` does not survive rescheduling.
