# 1. Context and Requirements

## 1.1 What changed since the Streamlit prototype

The prototype documented in `docs/deployment/` was a single
Streamlit web app calling Bedrock Knowledge Bases and Claude Sonnet
over `boto3`, intended for a multi-week internal demo. The redesign
in this directory differs in five concrete ways:

| # | Prototype | Redesign |
|---|---|---|
| 1 | Streamlit web UI is the only client. | **No web UI.** The backend exposes capabilities via MCP and is consumed by IDEs (Cursor, VS Code), Claude Desktop, agents, and any future custom client. |
| 2 | Single KB, single product. | **Two products today, more coming.** Multi-product partitioning is a first-class requirement, not a future migration. |
| 3 | Docs only. | **Docs + Snowflake table context.** Business data in Snowflake must be retrievable for grounded answers, across the bronze/silver/gold medallion layers. |
| 4 | AWS only. | **AWS and/or Snowflake.** Five designs evaluated, including Snowflake-only and hybrid. |
| 5 | Demo timeline. | **Targeted at a sustainable, multi-team backend** that can also serve the eventual agentic features. |

## 1.2 Functional requirements

F1. **Retrieve passages from codebase-generated documentation** for
two products today, growing.

F2. **Retrieve passages and answer questions over Snowflake tables**
at the gold medallion layer, with text-to-SQL where appropriate.

F3. **Cite sources** in every answer (doc URI for documents, table +
column lineage for tables, with the SQL run for analytical answers).

F4. **Expose all of the above as MCP tools** consumable from Cursor,
VS Code, Claude Desktop, and Cursor Cloud Agents. Optional REST
adapter for clients that cannot speak MCP yet.

F5. **Partition by product** at retrieval time. A caller passes a
product (or set of products) and the system answers only over that
scope, with metadata-filtered retrieval and per-product ACLs.

F6. **Support future write/mutating tools** (agentic actions on the
KBs and code) without changing the interface contract. New tools
plug in as MCP tools.

## 1.3 Non-functional requirements

N1. **Identity.** SSO via Okta for both end users (IDE-side) and
operators. Per-user identity is preserved end-to-end to the data
layer for audit.

N2. **Security posture.** No long-lived static credentials in any
client. Authoritative data layers (Bedrock KB, Snowflake) are
reached via short-lived tokens and IAM/RBAC.

N3. **Multi-tenant readiness within the org.** Different teams will
own different product KBs; tools must be discoverable and
authorisable per team.

N4. **Auditability.** Per-tool, per-user, per-call structured logs
in a central place. Every answer's citations are reproducible
months later (commit-pinned for docs, query-pinned for tables).

N5. **Operability.** Backend is idempotently re-deployable from
infrastructure-as-code; ingestion is re-runnable from raw inputs;
indices are rebuildable.

N6. **Cost predictability.** Bedrock and Cortex usage dominates;
the surrounding infra should not. Prefer managed services unless
self-management is cheaper *and* differentiating.

## 1.4 Inputs

- **Codebase-generated documentation** for the two products.
  Assumed shape: a doc-generation pipeline (separate workstream)
  produces a versioned tree per product on commits to that
  product's main branch. Output formats: Markdown, AsciiDoc, or
  HTML. Per-doc metadata available: product, repo, commit SHA,
  module/symbol path, last-modified.
- **Snowflake tables** belonging to those products. Already
  organised (or organisable) into bronze / silver / gold via the
  org's existing data-platform conventions.

## 1.5 Consumers

- **Engineers using Cursor or VS Code** — query docs and tables
  from the IDE while writing code.
- **Operators using Cursor Cloud Agents** — triage, evaluation
  runs, ops automations.
- **End users using Claude Desktop** (or similar MCP host) for
  ad-hoc Q&A on internal docs and data.
- **Future agents** (Bedrock Agents, LangGraph, custom) — consume
  the same MCP tools rather than re-implementing retrieval.

## 1.6 Decision drivers (ranked)

D1. **Multi-product, multi-source future fit.** The design must
not become an obstacle when adding products three, four, and five
or when adding non-codebase data sources.

D2. **Honour the data gravity.** Snowflake-resident table data
should not be exported wholesale just to satisfy AWS-side RAG
plumbing; conversely, codebase docs that already live in S3/git
should not be force-fit into Snowflake.

D3. **MCP-native end to end.** Every capability of the backend is
discoverable and invokable as an MCP tool. No "MCP for half the
features, REST for the other half" split.

D4. **Identity and audit.** End-user identity reaches the data
layer; every tool call is logged.

D5. **Operability cost.** Prefer managed services on each side of
the hybrid line; treat from-scratch as an explicit choice with a
specific justification.

D6. **Time to a usable backend for the two-product case.** Not the
fastest demo (that's the prior plan) but the fastest *production*
backend for the stated state.

## 1.7 Out of scope for this document

- The codebase doc-generation pipeline.
- LLM evaluation and guardrails framework (separate workstream).
- Production multi-region / DR.
- Exact pricing — qualitative cost only.
- Choice of agentic-orchestration framework (Bedrock Agents vs
  LangGraph vs custom). The MCP layer is the agent-agnostic
  surface; that choice happens above it.

## 1.8 Glossary

- **MCP** — Model Context Protocol. Open protocol for connecting
  LLM apps to context and tools. Two transports: stdio and
  Streamable HTTP. Primitives: tools, resources, prompts.
- **Bedrock KB** — Amazon Bedrock Knowledge Bases. Managed RAG
  service. Two flavours: *unstructured* (vector-based RAG over
  documents) and *structured* (NL→SQL over Redshift/Glue,
  introduced Dec 2024).
- **Cortex Search** — Snowflake's managed hybrid search service
  (vector + lexical), targeted at Snowflake-resident text.
- **Cortex Analyst** — Snowflake's managed text-to-SQL service with
  semantic-model files.
- **Cortex AISQL** — LLM functions callable from SQL inside
  Snowflake (e.g., `AI_COMPLETE`, `AI_CLASSIFY`).
- **Snowflake-managed MCP** — Snowflake's first-party MCP server
  GA'd 2025-11-04 via the `CREATE MCP SERVER` SQL object. Supports
  tool types `CORTEX_ANALYST_MESSAGE`, `CORTEX_SEARCH_SERVICE_QUERY`,
  Cortex Agents, custom tools, and SQL execution. OAuth + RBAC.
- **SPCS** — Snowpark Container Services. Snowflake's container
  hosting (run your own services inside the account boundary).
- **Medallion** — bronze (raw), silver (cleaned/conformed), gold
  (business-ready/served).
