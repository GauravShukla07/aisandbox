# aisandbox

Sandbox repo for the internal RAG chatbot prototype (Streamlit +
Bedrock Knowledge Bases + Claude Sonnet via `boto3`).

## Deployment planning

- [`docs/deployment/06-mcp-cursor-approach.md`](./docs/deployment/06-mcp-cursor-approach.md)
  — focused analysis of an **MCP + Cursor** approach for the demo
  (and the road to production): what it means, what it gives us,
  what it does not, three concrete adoption options, an explicit
  list of time-bounded uncertainties, and a build-plan delta over
  the broader hosting plan.

The broader hosting / authentication plan (approaches A–G, comparison
matrix, recommendation, etc.) lives in `docs/deployment/` and is
landed via a separate PR.
