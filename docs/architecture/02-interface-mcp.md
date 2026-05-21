# 2. Interface — MCP as the only front door

This chapter pins down the interface decision before any of the five
designs is evaluated, because the interface is invariant across them.

## 2.1 The interface contract (invariant across designs)

The backend exposes a fixed set of MCP **tools**, **resources**, and
**prompts**. Implementations on AWS, Snowflake, or both must satisfy
the same contract.

### 2.1.1 Tools (initial set)

| Tool | Purpose | Inputs | Outputs |
|---|---|---|---|
| `search_docs` | Hybrid retrieval over codebase documentation. | `query: str`, `products: [str]` (optional, default = caller's authorised set), `top_k: int = 8`, `filters: { doc_type?, module?, since?, until? }` | `[{passage, doc_uri, product, commit_sha, score, span}]` |
| `answer_from_docs` | RAG-style answer with citations, no SQL. | `query: str`, `products: [str]?`, `model: str?`, `top_k: int = 8` | `{answer, citations: [{doc_uri, product, commit_sha, span}], tokens, latency_ms}` |
| `search_tables` | Hybrid retrieval over gold-layer table descriptions / semantic model. | `query: str`, `products: [str]?`, `top_k: int = 8` | `[{table_fqn, column?, description, score}]` |
| `answer_from_tables` | Text-to-SQL answer with citations. | `query: str`, `products: [str]?`, `model: str?`, `max_rows: int = 1000` | `{answer, sql, columns, rows, citations: [{table_fqn, columns}], latency_ms}` |
| `answer_grounded` | Mixed answer using docs + tables; the model decides per-call which to draw from. | `query: str`, `products: [str]?`, `model: str?` | `{answer, citations: [...], tools_used: [...]}` |
| `list_products` | Catalogue of products the caller is authorised to query. | — | `[{product, description, owners, sources: [docs, tables]}]` |
| `list_doc_sources` | Per-product doc sources + freshness. | `product: str` | `[{source_uri, last_indexed, commit_sha, doc_count}]` |
| `list_table_sources` | Per-product gold table catalogue. | `product: str` | `[{table_fqn, layer, columns, description, last_indexed}]` |

Mutating ("agentic action") tools are deferred to a follow-on
chapter; they plug in here as additional tools without changing the
above.

### 2.1.2 Resources

URIs the caller (typically an IDE) can dereference for context:

- `docs://product/<product>/<commit>/<path>` — exact doc revision.
- `table://snowflake/<db>/<schema>/<table>` — table description +
  recent rows (with row-level masking applied as configured).
- `semantic-model://<product>` — the semantic-model file used by
  text-to-SQL (so the IDE can show the user what the model is
  matching against).

### 2.1.3 Prompts

- `cite_with_sources` — standard system prompt template that
  enforces inline citations.
- `sql_with_evidence` — system prompt for text-to-SQL responses
  that requires the answer to include the SQL and a one-line
  rationale.
- `cross_source_synthesis` — system prompt for `answer_grounded`
  combining docs and tables.

Pinning the prompts as MCP server primitives (not embedded in each
client) is a deliberate design choice. It centralises evaluation
and makes prompt regressions auditable.

## 2.2 MCP-only vs API-through-MCP

Two interface modes were considered. Either is implementable on top
of any of the five designs; the choice is independent.

### 2.2.1 Mode α — MCP-only (recommended)

The backend speaks MCP and nothing else. Streamable HTTP transport,
OAuth 2.1 + PKCE. Clients:

- **Cursor**: per-repo `.cursor/mcp.json` or global config; HTTP
  transport with bearer-token / OAuth auth (see §6.9 of the prior
  MCP chapter for verifiability caveats).
- **VS Code 1.99+**: workspace `.vscode/mcp.json` or user profile.
  Supports stdio and HTTP; supports full MCP including auth and
  sampling.
- **Claude Desktop**: `claude_desktop_config.json` with the HTTP
  endpoint.
- **Cursor Cloud Agents**: pick up the per-repo MCP config.
- **Future custom clients**: any MCP SDK (TypeScript, Python).

Advantages: one boundary, one auth model, one set of audit logs,
one schema surface. Removes the temptation to grow an out-of-band
REST surface that drifts from the MCP one.

### 2.2.2 Mode β — API-through-MCP (optional)

Build an OpenAPI-defined REST adapter in front of the same tool
implementations, generated from the same JSON Schemas the MCP tools
use. The MCP server and the REST server are two thin presentations
over the same tool functions.

This mode exists for two cases only:

1. A client that genuinely cannot speak MCP (e.g., a server-side
   batch job in a language without an MCP SDK).
2. A short transitional period when the org has tooling that
   integrates with REST but not MCP yet.

The risk of mode β: schema drift. Mitigation: generate both surfaces
from a single source of truth (the tool's JSON Schema) and run a CI
contract check that fails the build if the two diverge.

> Recommendation: ship mode α only at first. Add mode β if and only
> if a named consumer cannot speak MCP. Do not pre-emptively build
> a REST surface "in case."

## 2.3 The Snowflake-managed MCP server option

Verified facts about Snowflake's managed MCP (GA 2025-11-04):

- Created via SQL: `CREATE MCP SERVER` with a YAML spec listing
  tools. Lives as a Snowflake object.
- Tool types in the YAML include
  `CORTEX_ANALYST_MESSAGE` (Cortex Analyst as a tool),
  `CORTEX_SEARCH_SERVICE_QUERY` (Cortex Search as a tool), Cortex
  Agents, custom tools, and SQL execution.
- Authentication: OAuth via Snowflake's built-in OAuth service.
- Authorisation: Snowflake RBAC; the caller's role gates tool
  discovery and invocation.
- Protocol: MCP revision `2025-11-25` at GA.
- Companion open-source repo: `Snowflake-Labs/mcp` (Apache 2.0).

Implications for the design choices:

- In **Design C (Snowflake managed)**, the Snowflake-managed MCP is
  the entire serving plane. No external compute.
- In **Design E (hybrid)**, the Snowflake-managed MCP is one of the
  servers behind a federated MCP gateway. The other server speaks
  to AWS Bedrock KB.
- In **Designs A/B (AWS)** and **D (Snowflake self-managed)** the
  managed MCP server is irrelevant; a custom MCP server stands in
  for it.

Caveats:

- The contract surface of the managed MCP is parameterised by the
  YAML spec but is *not* arbitrary code. Custom tool behaviour that
  isn't expressible as a Cortex call or a SQL statement requires
  either (i) wrapping it in a Snowflake stored procedure / UDF
  registered as a custom MCP tool, or (ii) hosting the MCP server
  yourself (Design D).
- The tool input/output schemas exposed by `CORTEX_ANALYST_MESSAGE`
  and `CORTEX_SEARCH_SERVICE_QUERY` are determined by Snowflake.
  Aligning them to the §2.1.1 contract may require thin adapter
  tools written as SQL that re-shape inputs/outputs.

## 2.4 Authentication and authorisation

The interface contract requires:

- **AuthN**: OAuth 2.1 + PKCE bearer tokens; Okta is the IdP.
- **AuthZ**: tools discoverable based on the caller's role/group;
  per-product filtering enforced server-side, not client-side.

How each platform satisfies this:

- **AWS-side MCP server** (Designs A, B, and the AWS half of E):
  - Cognito User Pool federated to Okta SAML; Cognito hosts the
    OAuth 2.1 endpoints. The MCP server validates audience-bound
    bearer tokens and uses the token's `sub` to derive an AWS role
    via `AssumeRoleWithWebIdentity`. End-user identity reaches
    Bedrock KB and S3.
- **Snowflake-side MCP server** (Designs C, D, and the Snowflake
  half of E):
  - Snowflake's built-in OAuth (Snowflake as the OAuth server)
    federated to Okta. The caller's Snowflake role gates tool
    discovery and execution; per-product authorisation is RBAC on
    the underlying Cortex Search service, Cortex Analyst semantic
    model, and gold tables. Row-access policies on the gold tables
    enforce row-level masking by `current_role()`.
- **Hybrid (Design E)**:
  - The federated MCP gateway is itself an OAuth 2.1 resource
    server. The gateway validates the caller's Okta-issued token,
    then mints downstream tokens for the AWS and Snowflake MCP
    servers via on-behalf-of (token exchange, RFC 8693), so each
    downstream server sees a token bound to its own audience and
    the caller's `sub`.

The end-to-end identity chain (Okta → backend → AWS or Snowflake →
data) is the same in all three; what differs is who is the OAuth
server (Cognito on AWS, Snowflake on Snowflake, the gateway in
hybrid).

## 2.5 Audit trail

Every tool call produces a structured event with:

- `tool`, `version`, `request_id`, `parent_request_id` (for
  agent-chained calls).
- `caller.sub`, `caller.email`, `caller.role`, `client` (Cursor /
  VS Code / Claude Desktop / agent name).
- `products: [...]` requested vs `products: [...]` authorised.
- `inputs.hash` (do not log full prompts at INFO; redact at WARN).
- `outputs.summary` (size, citation count, success flag).
- `latency_ms`, `tokens.{input,output}`, `cost_estimate_usd`.
- Pointers: `bedrock.kb_request_id` / `snowflake.query_id` for
  reproducing the underlying retrieval.

Where this lands:

- AWS-side: CloudWatch Logs, with a Logs Insights query collection.
- Snowflake-side: `EVENT_TABLE`s (Cortex events) plus
  `QUERY_HISTORY` for SQL traceability.
- Hybrid: the gateway emits a unified event in addition to each
  side's native log; the unified event has the cross-side
  correlation IDs.
