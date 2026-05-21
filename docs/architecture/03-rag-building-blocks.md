# 3. RAG building blocks

This chapter is platform-agnostic: it inventories the choices we
have to make about vector stores, chunking, indexing, retrieval,
and metadata, and chooses defaults that the five designs in chapters
5–9 then specialise.

## 3.1 Vector store options

### 3.1.1 Managed (AWS)

Bedrock Knowledge Bases natively integrates with the following
vector stores (verified against the `StorageConfiguration` API
enum):

| Store | Index type | Filters | Hybrid (BM25 + vector) | Operational shape | Notes |
|---|---|---|---|---|---|
| **OpenSearch Serverless** | HNSW (FAISS / nmslib) | Yes | Yes (BM25 + kNN) | Fully managed, capacity-unit billed | Default Bedrock KB choice; widely deployed. |
| **OpenSearch Managed Cluster** | HNSW | Yes | Yes | Managed cluster, instance-billed | GA Mar 2025 for Bedrock KB; better cost control at high scale. |
| **Aurora (RDS) pgvector** | HNSW or IVFFlat | Yes (SQL `WHERE`) | Limited (needs trigram / pg_trgm or `ParadeDB`/`pgsearch`) | Managed Postgres | Best when the team already runs Aurora; SQL filters are very expressive. |
| **Neptune Analytics** | Vector index on a graph | Yes (graph filters) | Limited | Managed graph DB with vector index | Use only if the KB is genuinely graph-shaped. |
| **Pinecone** | Proprietary HNSW | Yes (rich metadata filters) | Yes (sparse + dense) | Third-party SaaS | Strong DX, mature; data egresses AWS account. |
| **MongoDB Atlas** | Atlas Vector Search | Yes | Yes (Atlas Search + vector) | Third-party SaaS / Atlas on AWS | Reasonable when MongoDB is already adopted. |
| **Redis Enterprise Cloud** | HNSW (RediSearch) | Yes | Yes | Third-party SaaS | Lowest read latency in the list. |
| **S3 Vectors** | Bucket-native vector index | Limited | No (vector only) | Fully managed, S3-pricing-shaped | Newer; conservative posture is "use for cold KBs or large but quiet corpora." |

### 3.1.2 Managed (Snowflake)

| Service | Mechanism | Filters | Hybrid | Notes |
|---|---|---|---|---|
| **Cortex Search** | Managed hybrid (vector + lexical) over Snowflake tables. | Yes (SQL `WHERE` on backing table) | Yes (built-in) | First-party Snowflake; ranks via a tuned hybrid model. |
| **Cortex Search + Cortex Analyst combo** | Cortex Search for text passages; Cortex Analyst for structured Q&A. | Yes | Yes | The two together are the standard Snowflake RAG-on-tables pattern. |

### 3.1.3 Self-managed / independent

| Store | Index type | Hybrid | Where it lives | Notes |
|---|---|---|---|---|
| **Postgres + pgvector** (self-managed) | HNSW / IVFFlat | With `pg_trgm` or extensions | RDS / EC2 / SPCS | Choose when you want SQL-first filters and join-with-other-tables. |
| **OpenSearch / Elasticsearch (self-managed)** | HNSW | Native BM25 + vector | EC2 / EKS / SPCS | Pick when an OpenSearch team already exists. |
| **Qdrant** | HNSW + payload index | Native sparse + dense | EC2 / EKS / SPCS | Excellent metadata filter performance. |
| **Weaviate** | HNSW | Native hybrid | EC2 / EKS / SPCS | Built-in modules (rerank, multimodal). |
| **Milvus** | HNSW / IVF / DiskANN | Limited | EKS / SPCS | Best for very large corpora (>100M vectors). |
| **Chroma / LanceDB** | HNSW | Limited | Local / single-node | Avoid for production multi-tenant. |

### 3.1.4 Default choice per design

- **Design A (AWS managed):** OpenSearch Serverless. Strongest
  Bedrock-KB integration, hybrid retrieval, metadata filtering.
- **Design B (AWS self-managed):** Aurora pgvector. SQL filters
  match the multi-product partitioning model; cheaper than
  OpenSearch at low-to-medium scale.
- **Design C (Snowflake managed):** Cortex Search over a docs
  table; Cortex Analyst over the gold tables.
- **Design D (Snowflake self-managed):** Qdrant on Snowpark
  Container Services for docs; Cortex Analyst remains the table-Q&A
  path.
- **Design E (hybrid):** Bedrock KB on OpenSearch Serverless for
  code docs (data gravity = S3/git); Cortex Search + Cortex
  Analyst for tables (data gravity = Snowflake).

### 3.1.5 Managed vs independent — when to take which

Choose managed when:

- The team is small (no dedicated vector-DB operator).
- Latency and recall targets are met by the default tuning.
- The vector store is one of many RAG components and you do not
  want it to be the differentiator.

Choose independent when:

- You need a feature not in the managed offering (e.g., a custom
  ANN index, a specific rerank pipeline, exotic metadata filters).
- The corpus is large enough that managed per-unit pricing is
  meaningfully more expensive than running a tuned cluster.
- The vector store *is* the differentiator (research lab, public
  product).

For this app at two products and growing: **managed wins on every
axis.** Keep the door open to self-management by treating the
vector store behind an in-process repository interface
(`VectorStoreRepo`) so a swap is mechanical.

## 3.2 Chunking strategies

### 3.2.1 The chunking choices Bedrock KB exposes (managed path)

Bedrock KB exposes these chunking modes when configuring an
unstructured data source:

- **Default** — fixed-size with overlap (~300 tokens, ~20% overlap).
- **Fixed-size** — explicit token-count and overlap.
- **Semantic** — model-based; finds boundaries by semantic
  similarity.
- **Hierarchical** — parent-child; parent chunks indexed for
  retrieval, child chunks indexed for ranking; on hit, the parent
  is returned.
- **No chunking** — one chunk per file.

### 3.2.2 The chunking choices Cortex Search exposes

Cortex Search indexes a designated text column from a Snowflake
table. Chunking is an upstream concern: produce one row per chunk
in the source table (silver→gold transformation), and Cortex Search
ranks over those rows. This makes chunking strategy a property of
the *ingestion pipeline*, not the search service.

### 3.2.3 Recommended chunking strategy for codebase docs

Codebase-generated documentation has three structural levels:

1. **Module / namespace** — coarse.
2. **Symbol** (class, function, struct) — medium.
3. **Paragraph or example block within a symbol** — fine.

Recommended: **hierarchical chunking with code-aware boundaries.**

- *Parent chunk* = one symbol's full documentation (class,
  function, struct), including its signature, parameters, return
  values, examples, and any narrative text immediately under it.
  Typical size: 200–800 tokens.
- *Child chunk* = each distinct paragraph / code example within
  the parent. Typical size: 30–200 tokens.

Retrieval ranks over children but returns parents — so the model
sees enough context to write a useful answer, while ranking happens
on tightly-scoped passages.

Boundary rules:

- Never split a code block.
- Never split a parameter table.
- Never split a sentence.
- Strip navigation chrome (headers/footers, sidebars) at the
  silver-layer transformation, not at indexing time.

### 3.2.4 Recommended chunking strategy for Snowflake table context

For tables, "chunks" are not the row data itself; they are
descriptions of tables and columns:

- One row per **table** with: `table_fqn`, `description`,
  `business_owner`, `column_descriptions` (joined string),
  `example_queries` (joined), `last_updated`.
- One row per **column** with: `table_fqn.column`, `data_type`,
  `description`, `enum_values?`, `example_values?`.

Cortex Search ranks these rows. Cortex Analyst uses the semantic
model file in parallel for text-to-SQL. The two work together:
search finds relevant tables; Analyst generates the SQL.

For Design B (AWS self-managed), the same row shape can be loaded
into pgvector / Qdrant.

### 3.2.5 Why not just "embed the whole file"?

Tested, doesn't work for non-trivial docs:

- Recall drops because the embedding averages across multiple
  symbols.
- Citation precision drops; the model can't point to a span.
- Context windows are wasted by retrieving large parent chunks
  when only a function's signature was relevant.

## 3.3 Indexing and hybrid retrieval

### 3.3.1 Index types

For all designs, the recommended index is **HNSW** (Hierarchical
Navigable Small Worlds). Reasons:

- Available in every store under consideration.
- Sub-linear query time at the scales we expect (≤ 10M chunks).
- Tunable recall/latency via `ef_search` / `ef_construction`.

IVFFlat (in pgvector specifically) is a fallback when build time
matters more than query time. At our scale, build time is not a
constraint.

### 3.3.2 Hybrid retrieval (BM25 + vector)

Hybrid retrieval consistently outperforms pure-vector on
code-documentation corpora because:

- Exact symbol names ("foo_bar_v2") are lexically distinctive in
  ways embeddings smooth over.
- Code samples contain literal tokens that BM25 ranks very well.

All designs target hybrid retrieval. How:

- **OpenSearch / Cortex Search**: native hybrid; provide a query
  and the engine ranks BM25 + vector with a tunable weight.
- **pgvector**: combine `pgvector` similarity with `pg_trgm` or
  `ParadeDB`/`pgsearch` BM25; rank-fuse client-side using
  reciprocal-rank fusion (RRF).
- **Qdrant / Weaviate**: native hybrid.

### 3.3.3 Reranking

A cross-encoder rerank pass on the top-50 hybrid results, returning
the top-8 for the LLM, raises citation precision noticeably. Costs:

- AWS: Cohere Rerank on Bedrock (managed model).
- Snowflake: Cortex Search built-in reranker (Snowflake-managed).
- Self: any sentence-transformer cross-encoder on a small GPU /
  CPU service.

Default: enable rerank in all designs. Make it toggleable per
request so latency-sensitive tools (autocomplete in an IDE) can
skip it.

## 3.4 Metadata strategy

Metadata is what makes multi-product partitioning,
freshness-filtering, and audit work. It has to be designed once.

### 3.4.1 Canonical metadata schema for doc chunks

```yaml
chunk_id: <uuid>
parent_chunk_id: <uuid?>            # for hierarchical
product: <str>                       # e.g. "product-alpha"
repo: <str>                          # e.g. "github.com/org/alpha"
commit_sha: <str>                    # the doc snapshot's commit
path: <str>                          # path inside the doc tree
doc_type: <enum>                     # readme|api_ref|runbook|tutorial|adr
module: <str?>                       # e.g. "alpha.auth.tokens"
symbol: <str?>                       # e.g. "TokenIssuer.issue"
language: <str?>                     # e.g. "python", "typescript"
last_modified: <iso-8601>
generated_at: <iso-8601>             # when the doc was generated
indexed_at: <iso-8601>               # when this chunk was indexed
acl_tags: [<str>...]                 # e.g. ["product-alpha","public-internal"]
checksum: <sha256>
```

### 3.4.2 Canonical metadata schema for table descriptions

```yaml
row_id: <uuid>
product: <str>
table_fqn: <str>                     # e.g. "ANALYTICS.GOLD.ORDERS"
layer: <enum>                        # bronze|silver|gold
column: <str?>                       # null for table-level rows
data_type: <str?>                    # for column-level rows
description: <str>
business_owner: <str>
example_values: [<str>...]?
example_queries: [<str>...]?
acl_tags: [<str>...]
last_updated: <iso-8601>
indexed_at: <iso-8601>
```

### 3.4.3 Use of metadata

- **Pre-filter retrieval** by `product`, `doc_type`, `layer`. This
  is the multi-product partitioning point.
- **Post-rank filter** by `acl_tags` against the caller's group
  set. Defence in depth: retrieval pre-filters by product;
  post-rank filter enforces row-level ACLs that the pre-filter
  alone cannot.
- **Citation** uses `product`, `repo`, `commit_sha`, `path`, and
  `span` for docs; `table_fqn`, `column`, `query_id` for tables.
- **Freshness windows** use `last_modified` and `indexed_at`.

### 3.4.4 Multi-product partitioning at the index layer

Two viable shapes:

- **One index, metadata-filtered.** All products share a single
  vector index; queries pre-filter by `product`. Simplest; the
  managed services support it.
- **One index per product.** Strong isolation; harder to do
  cross-product `answer_grounded` queries cleanly.

Default: **one index, metadata-filtered**, with `acl_tags`
enforcing row-level visibility. Move to per-product indices only
if (a) ACLs become irreducibly per-product and the metadata-filter
approach is too coarse, or (b) corpus size in one product is large
enough to warrant its own tuning.

### 3.4.5 Cross-source metadata join

The `product` field is shared between docs and tables. That is what
lets `answer_grounded` say "for product alpha, the table
`ANALYTICS.GOLD.ORDERS_DAILY` has the figure the documentation
calls 'daily orders' — here is the SQL and the citation."

Coherent `product` values across both sides are a hard requirement.
Treat the product taxonomy as a contract maintained somewhere both
sides read from (the simplest place: a small YAML in this repo,
checked into both sides' ingestion pipelines).

## 3.5 Embedding model choices

| Path | Embedding model | Dimension | Notes |
|---|---|---|---|
| AWS managed | Amazon Titan Text Embeddings v2 (1024) or Cohere Embed v3 (1024) | 1024 | Bedrock-hosted; pinned per KB. |
| AWS self | Same as above via Bedrock | 1024 | Avoid running embedding compute yourself unless you must. |
| Snowflake managed | Cortex `EMBED_TEXT_*` functions or Cortex Search's built-in | model-defined | Embeddings live inside Snowflake; no egress. |
| Snowflake self | Same Cortex functions or BYO embedding via UDF | depends | Prefer Cortex unless there's a specific need. |
| Hybrid | One on each side; never share an index across embedding models | depends | The federated retrieval combines results, not vectors. |

Rules of thumb:

- Never mix embedding models inside one index.
- Re-index when you change embedding model.
- Use `commit_sha` + `embedding_model_version` to make
  re-indexing safe and idempotent.
