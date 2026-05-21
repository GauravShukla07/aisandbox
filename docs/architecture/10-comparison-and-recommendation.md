# 10. Comparison and Recommendation

## 10.1 Weighted comparison matrix

Each design (A–E) is scored against the decision drivers in
[`01-context.md` §1.6](./01-context.md#16-decision-drivers-ranked).
Higher is better. Weights reflect the org's stated state: two
products today, tables in Snowflake, docs in S3/git, growing.

| Driver | Weight | A — AWS managed | B — AWS self-managed | C — Snowflake managed | D — Snowflake self-managed | E — Hybrid |
|---|---:|---:|---:|---:|---:|---:|
| D1 Multi-product / multi-source future fit | 5 | 3 | 3 | 3 | 3 | **5** |
| D2 Honour data gravity (docs + tables) | 5 | 2 | 2 | 3 (only if docs move to SF) | 3 (same caveat) | **5** |
| D3 MCP-native end to end | 4 | 4 | 4 | **5** | 4 | **5** |
| D4 Identity & audit | 4 | 4 | 4 | **5** | 4 | 4 |
| D5 Operability cost | 4 | 4 | 2 | **5** | 3 | 3 |
| D6 Time to a usable backend | 3 | **5** | 3 | 4 | 2 | 3 |
| **Total (weighted)** |  | 79 | 65 | 90 (with docs-in-SF caveat) | 71 | **95** |

Interpretation:

- **C** scores highest *only if* moving the codebase docs into
  Snowflake is acceptable. For the stated org state (docs in git/S3),
  C's effective score drops because moving docs is friction.
- **E** wins on the actual stated state. It is the design that
  doesn't penalise either side's data gravity.
- **A** is the natural fallback if the team decides "we'll do
  tables on AWS too via replication for now and revisit." It pays
  ongoing dual-warehouse cost and replication-lag risk.
- **B** is dominated by **A** unless a specific technical reason
  forces self-management.
- **D** is dominated by **C** unless a specific technical reason
  forces a custom MCP server.

## 10.2 Recommendation

**Build Design E (hybrid) behind a federated MCP gateway.** The
two halves are exactly Design A (AWS, doc tools only) and Design C
(Snowflake, table tools only). The gateway is a small stateless
Fargate service.

Reasons:

1. **Data gravity.** Docs already live where AWS RAG plumbing is
   natural; tables already live in Snowflake. Moving either is a
   cost with no benefit at the current state.
2. **First-class table Q&A.** Cortex Analyst on Snowflake is the
   simplest path to grounded analytical answers. Reproducing it on
   AWS would be a non-trivial subproject.
3. **Future fit.** Adding more products is one taxonomy-YAML row
   plus per-side ingestion + RBAC. Adding more data sources is one
   more MCP server behind the gateway.
4. **Reversible.** If the org later consolidates on one platform,
   the gateway becomes a thin proxy on that side; no rewrite.
5. **MCP-native.** Clients see one MCP endpoint. They don't know
   or care about the two planes.

## 10.3 Staged rollout plan

The rollout is **four stages**. Each stage is a self-contained
deliverable; the backend produces value at the end of every stage.

### Stage I — AWS-side doc tools only

Goal: `search_docs`, `answer_from_docs` end-to-end via the
AWS-side MCP server, no gateway yet. Clients point directly at
the AWS MCP for now.

- Execute Design A Stages 1–5 (omit structured KB / Redshift).
- Onboard one product first; smoke test with Cursor, VS Code,
  Claude Desktop.
- Outcome: users can query codebase docs from any MCP client.

### Stage II — Snowflake-side table tools only

Goal: `search_tables`, `answer_from_tables` end-to-end via the
Snowflake managed MCP server, no gateway yet. Clients can either
point at the Snowflake MCP directly (two endpoints in their
`mcp.json`) or wait for Stage III.

- Execute Design C Stages 1–6, scoped to table tools (no docs).
- Onboard the same first product to validate the product taxonomy
  YAML cross-side.
- Outcome: users can query gold tables.

### Stage III — Federated gateway

Goal: one MCP endpoint per client; `answer_grounded` works.

- Execute Design E Stage 3 (gateway).
- Cut over clients to the gateway endpoint.
- Decommission the direct AWS / Snowflake MCP endpoints from
  client configurations (the servers remain; just not exposed
  directly).
- Outcome: one MCP endpoint; cross-source synthesis works.

### Stage IV — Onboarding for the second product, then more

Goal: scale to N products without architectural change.

- Add second product to the taxonomy YAML.
- Trigger AWS docs ingestion for the second product.
- Add Snowflake semantic model, Cortex Analyst service, Cortex
  Search service if used, and role grants for the second product.
- Outcome: two-product steady state.
- Repeat for product three, four, … on the same template.

Future-stage (out of scope here):

- Mutating / agentic action tools (`actions-mcp`) added as a third
  MCP server behind the gateway.
- Cross-region replication for DR.

## 10.4 Comparison: vector stores in this recommendation

Per design within E:

- **AWS half.** OpenSearch Serverless. The default Bedrock KB
  store; hybrid retrieval, metadata filtering, managed lifecycle.
- **Snowflake half.** Cortex Search where doc-style search is
  needed (only for table descriptions in this design, since docs
  themselves live on AWS). Cortex Analyst handles structured Q&A.

If the AWS half later needs different vector-store characteristics
(e.g., a strict cost target on a very large doc corpus), swap
OpenSearch Serverless for Aurora pgvector — Design B's pattern,
applied just to the AWS half.

## 10.5 Comparison: chunking and indexing in this recommendation

- **Docs (AWS half).** Hierarchical chunking. Bedrock KB exposes
  hierarchical chunking as a built-in mode; use it. Parent =
  symbol; child = paragraph/example. HNSW under the hood.
- **Tables (Snowflake half).** Row-per-table and row-per-column
  description rows in `GOLD.<PRODUCT>_TABLE_DESC`. Cortex Search
  ranks rows. Cortex Analyst is text-to-SQL over the gold tables
  themselves; no chunking of row data.

## 10.6 Comparison: metadata strategy

Common metadata schema across both halves (§3.4). The
**`product`** field is the cross-side join key. Per-product RBAC is
implemented natively on each side; the gateway enforces it again
as defence-in-depth.

## 10.7 Comparison: managed vs from-scratch

In the recommended design, both halves are managed:

- AWS half is managed where it matters (Bedrock KB + OpenSearch
  Serverless + Bedrock Runtime). The MCP server is the only custom
  thing on the AWS half.
- Snowflake half is fully managed (managed MCP, Cortex Search,
  Cortex Analyst, Cortex AISQL).

The gateway is a small custom service. This is the only piece that
is not "from a managed service" — and it is small (a few hundred
lines of MCP-routing code) and stateless, so the operational cost
is minimal.

From-scratch would be a step backwards here: the team would
re-implement chunking, vector retrieval, reranking, text-to-SQL,
and authentication that the managed services already do correctly.

## 10.8 Open questions (timed)

To convert this plan into a build, the following decisions must be
made by the team:

1. **Cognito-vs-Snowflake-OAuth token exchange viability.** Run a
   one-week spike on RFC 8693 token exchange between Cognito and
   Snowflake OAuth. Decide between (i) true token exchange and (ii)
   the service-principal + signed-assertion fallback (§9.6).
2. **Cortex model choice.** Pick the LLM for Cortex AISQL synthesis
   on the Snowflake half (Claude vs Llama vs Mistral). Constrained
   by what is available in the chosen Snowflake region.
3. **Bedrock model choice.** Pick the synthesis model for the AWS
   half and for the gateway's `answer_grounded` synthesis (Claude
   Sonnet vs Opus; latency/cost trade-off).
4. **Hosting of the gateway.** Default: Fargate. Reconsider if the
   org adopts a serverless-first stance.
5. **Doc-generation contract.** What does each product's CI emit?
   This is the inbound boundary of the bronze layer; nailing it
   down early avoids a re-ingest later.

## 10.9 What success looks like

The backend is "done for the two-product case" when:

- Every §2.1 MCP tool is callable from Cursor, VS Code, and Claude
  Desktop with end-user identity preserved into AWS and Snowflake.
- A query like *"How do we compute daily active users for product
  alpha, and what's last week's number?"* produces an answer with
  both a doc citation (the metric definition) and a table citation
  (the SQL + rows from `GOLD.ALPHA.ORDERS_DAILY`).
- Adding product gamma is a checked-in PR + a Snowflake role grant
  — no architectural change.
- A failure on either plane degrades cleanly: doc questions still
  work if Snowflake is down; table questions still work if AWS is
  down; `answer_grounded` returns partial results with
  `tools_used` accurately listed.

## 10.10 What this plan does **not** commit to

- Specific dollar costs. Cost modelling is a follow-on workstream
  per the §1.7 scope.
- Specific MCP spec revision pinning beyond "use the revision the
  Snowflake-managed MCP requires" on the Snowflake side and "pin
  whatever the AWS-side MCP server library supports" on the AWS
  side.
- A choice between Bedrock Agents, LangGraph, or custom for the
  later agentic-actions tools. That is a separate workstream that
  consumes this set's MCP surface, not a redesign of it.
- Service-level objectives. SLOs depend on org-wide expectations
  that are out of scope.

## 10.11 Verifiability note

The following claims were verified against current documentation at
the time of writing and should be re-verified before commitment:

- Snowflake-managed MCP server GA on 2025-11-04; SQL object
  `CREATE MCP SERVER`; YAML-defined tools including
  `CORTEX_ANALYST_MESSAGE`, `CORTEX_SEARCH_SERVICE_QUERY`, Cortex
  Agents, custom tools, SQL execution; OAuth-based auth via
  Snowflake's built-in OAuth; RBAC governs tool discovery and
  invocation; MCP revision 2025-11-25.
- Bedrock KB vector stores currently supported per the
  `StorageConfiguration` enum: OpenSearch Serverless, OpenSearch
  Managed Cluster (GA Mar 2025), Aurora RDS (pgvector), Neptune
  Analytics, Pinecone, MongoDB Atlas, Redis Enterprise Cloud,
  S3 Vectors.
- Bedrock KB structured data source (launched Dec 2024): query
  engine is Amazon Redshift (Provisioned or Serverless); data
  store options are Redshift or AWS Glue Data Catalog (incl. S3).
  No direct Snowflake source today.
- VS Code MCP support: `.vscode/mcp.json` (workspace) or user
  profile; requires VS Code ≥ 1.99; supports the full MCP spec
  (tools, prompts, resources, authorisation, sampling) as of
  June 2025.
- Cursor MCP support: `.cursor/mcp.json` per-repo, with stdio and
  HTTP transports.

Service surfaces continue to evolve; treat the items above as the
**state at the time of authoring**, not a permanent contract.
