import type {
  AgentFrameworkStep,
  AiProvider,
  ApiKeyItem,
  ApiRoute,
  ArchitectureEdge,
  ArchitectureNodeData,
  AuthMechanism,
  BackendModule,
  CloudService,
  EnvVar,
  FrontendInfo,
  KpiItem,
  PackageItem,
  PaymentStep,
  PromptTemplate,
  Recommendation,
  RepoMeta,
  SecurityClean,
  SecurityFinding,
  Worker,
} from "@/types/report";

// Every fact below was verified directly against the governedmemory repo
// (github.com/Metaworkers-ai/governedmemory) — file:line references point
// at the code each claim is drawn from. Earlier report content described a
// different, unrelated codebase (Square/Twilio/Shopify connectors); this
// repo has none of that. It's a FastAPI REST server (api/) fronting a
// governed agent-memory store (core/memory_store) on Postgres+pgvector,
// with no user-account system — auth is one static Bearer API key per
// tenant (api/auth.py).

export const repoMeta: RepoMeta = {
  name: "governedmemory",
  owner: "Metaworkers-ai",
  branch: "main",
  commit: "7245988",
  clonedDate: "2026-08-06",
  lastCommitDate: "2026-08-05",
  trackedFiles: 253,
  pythonLoc: 21297,
  backendStack: "FastAPI",
  frontendStack: "Next.js (App Router)",
};

export const repoScore = 80;

export const aiProviders: AiProvider[] = [
  {
    provider: "OpenAI",
    sdk: "openai SDK (OpenAIEmbeddingProvider)",
    model: "text-embedding-3-small (default) — OPENAI_EMBEDDING_MODEL to override, EMBEDDING_DIM truncates via the API's `dimensions` param",
    file: "api/main.py:_build_embedder:65-73, core/memory_store/embeddings.py:130",
    purpose:
      "First-choice real semantic search, used only if OPENAI_API_KEY is set. The key is read server-side by the OpenAI SDK's own env lookup and never exposed to a frontend.",
    referenceCount: 1,
  },
  {
    provider: "sentence-transformers (local)",
    sdk: "sentence-transformers (optional extra, requirements-embed-local.txt)",
    model: "all-mpnet-base-v2, 768-dim, hardcoded default — the documented EMBEDDING_MODEL env var is not actually read here",
    file: "api/main.py:_build_embedder:75-79, core/memory_store/embeddings.py:58-94",
    purpose:
      "No-API-key fallback when the embed-local extras are installed; runs on CPU or GPU.",
    referenceCount: 1,
  },
  {
    provider: "NullEmbeddingProvider",
    sdk: "none",
    model: "n/a — returns all-zero 768-dim vectors",
    file: "api/main.py:_build_embedder:79-80, core/memory_store/embeddings.py:102-122",
    purpose:
      "Final fallback so the API server always starts even with no embedding provider configured; vector search quietly degrades to arbitrary results instead of the server failing to boot.",
    referenceCount: 1,
  },
];

export const aiNotFound = [
  "Anthropic",
  "Google Gemini",
  "Azure OpenAI",
  "OpenRouter",
  "Ollama",
  "Together AI",
  "Groq",
  "Mistral",
  "Hugging Face",
  "DeepSeek",
  "xAI",
  "LangChain / CrewAI / LlamaIndex / AutoGen (no agent framework used)",
];

export const aiFlow = [
  { label: "Write request", detail: "POST /v1/memory or an external-memory evaluate-write call" },
  { label: "Write governor", detail: "core/write_governor — dedup + injection scan before persistence" },
  { label: "Embedding provider", detail: "OpenAI → local sentence-transformers → zero-vector, first available wins" },
  { label: "Persist", detail: "core/memory_store writes to Postgres, vector(768) column via pgvector" },
  { label: "Retrieval", detail: "core/retrieval_engine fuses vector + lexical (FTS) search results" },
  { label: "Governance gate", detail: "core/policy_engine filters by purpose-binding before results return" },
];

export const backendModules: BackendModule[] = [
  {
    name: "api",
    path: "api/",
    role: "HTTP surface",
    status: "working",
    description: "FastAPI app, 20 routes, Bearer API-key auth (api/auth.py), no CORS middleware configured.",
    dependsOn: ["core/memory_store"],
  },
  {
    name: "memory_store",
    path: "core/memory_store/",
    role: "Persistence + orchestration",
    status: "working",
    description: "Raw psycopg2 (no ORM). init_db() runs idempotent DDL for memory/audit/external_governance_operations/external_memory_bindings/policy tables, pgvector ivfflat index + tsvector FTS index.",
    dependsOn: ["core/write_governor", "core/retrieval_engine", "core/policy_engine", "core/audit"],
  },
  {
    name: "write_governor",
    path: "core/write_governor/",
    role: "Write-time governance",
    status: "working",
    description: "Duplicate detection (find_duplicate) and prompt-injection scanning (scan_for_injection), invoked inside MemoryStore.write().",
    dependsOn: ["core/detection"],
  },
  {
    name: "detection",
    path: "core/detection/",
    role: "Injection scoring",
    status: "working",
    description: "score_injection() classifier used at write time; INJECTION_THRESHOLD (default 0.7) marks a write untrusted.",
  },
  {
    name: "retrieval_engine",
    path: "core/retrieval_engine/",
    role: "Governed search",
    status: "working",
    description: "Reciprocal-rank-fusion of vector + lexical search, plus privilege-gate filtering, used inside MemoryStore.retrieve().",
  },
  {
    name: "policy_engine",
    path: "core/policy_engine/",
    role: "Purpose-binding governance",
    status: "working",
    description: "evaluate_purpose_binding / evaluate_privileged_action / filter_by_purpose_binding — used internally by retrieve()/check_privilege(), not yet exposed as its own route.",
  },
  {
    name: "audit",
    path: "core/audit/",
    role: "Provenance + tamper-evidence",
    status: "working",
    description: "Hash-chained append-only audit log (verify_chain in verifier.py, not yet routed), cascade-purge planning, and provenance-graph walking over parent_ids.",
  },
  {
    name: "governance",
    path: "core/governance/",
    role: "External-write evaluation",
    status: "working",
    description: "GovernanceEvaluationService/Request domain model backing all /v1/external-memories/* routes (e.g. the Mem0 adapter integration).",
  },
];

export const frontendInfo: FrontendInfo = {
  framework: "Next.js",
  version: "This dashboard: 16.3.0 (App Router). governedmemory also ships web/, a separate Next.js console.",
  routing: "App Router, Server Components for reads, no client-side routing library.",
  pages: [
    { path: "web/app/write", purpose: "Write a memory (Server Action)" },
    { path: "web/app/browse", purpose: "Customers → memories, server-fetched from /v1/customers and /v1/memories" },
    { path: "web/app/search", purpose: "Governed retrieve(), client-triggered Server Action" },
    { path: "web/app/governance", purpose: "Quarantine / delete a memory" },
    { path: "web/app/audit", purpose: "Audit log, server-fetched from /v1/audit" },
    { path: "web/app/signup", purpose: "UI-only stub — no account-creation endpoint exists yet (see web/app/signup/page.tsx:72-75)" },
  ],
  components: ["web/lib/backend.ts (server-only fetch wrapper)", "web/app/actions.ts (Server Actions for mutations)", "ContextBar (localStorage-backed customer/agent/session picker)"],
  configFiles: ["web/next.config.ts", "web/tsconfig.json", "web/.env.example"],
  note:
    "web/ talks to the REST API over plain HTTP with the Bearer-key pattern and has no dependency on core/Postgres/Python. It's single-tenant-per-deployment: tenant_id comes entirely from the configured API key, so there's no tenant switcher in the UI. This dashboard (metaworkers-dashboard) is a separate, read-mostly reporting console on the same backend.",
};

export const packages: PackageItem[] = [
  { name: "fastapi", version: ">=0.115,<1.0", category: "Backend", purpose: "HTTP surface framework (api/main.py)", status: "working" },
  { name: "uvicorn[standard]", version: ">=0.32.0", category: "Backend", purpose: "ASGI server — `make api` runs uvicorn api.main:app", status: "working" },
  { name: "pydantic", version: ">=2.9.0,<3.0", category: "Backend", purpose: "Request/response schemas (api/schemas.py) and core/models", status: "working" },
  { name: "psycopg2-binary", version: ">=2.9.9", category: "Database", purpose: "Postgres driver, no ORM — core/memory_store uses raw SQL", status: "working" },
  { name: "pgvector", version: ">=0.3.0", category: "Database", purpose: "Python type adapter for the vector(768) column + ivfflat index", status: "working" },
  { name: "python-dotenv", version: ">=1.0.0", category: "Utilities", purpose: "Loads DATABASE_URL and other env vars from .env", status: "working" },
  { name: "openai", version: ">=1.0.0", category: "AI", purpose: "OpenAIEmbeddingProvider — only imported if OPENAI_API_KEY is set", status: "working" },
  { name: "sentence-transformers", version: ">=3.0.0", category: "AI", purpose: "Optional local embedding fallback (requirements-embed-local.txt)", status: "partial" },
  { name: "torch", version: ">=2.0.0", category: "AI", purpose: "CPU/GPU backend for sentence-transformers", status: "partial" },
  { name: "mem0ai", version: "==2.0.12", category: "External SDK", purpose: "Pinned version behind sdk/python/metaworkers/adapters/mem0.py's contract test", status: "working" },
  { name: "agentdojo", version: "==0.1.35", category: "External SDK", purpose: "AgentDojo attack-benchmark harness, integrations/agentdojo", status: "working" },
  { name: "streamlit", version: ">=1.38", category: "Frontend", purpose: "Legacy demo UI (frontend/app.py) — talks to MemoryStore in-process, predates the REST API", status: "working" },
  { name: "pytest / pytest-cov", version: ">=8.0 / >=5.0", category: "Testing", purpose: "Test runner + coverage, 39 test files", status: "working" },
  { name: "testcontainers[postgres]", version: ">=4.7", category: "Testing", purpose: "Spins up a real Postgres+pgvector container for integration tests", status: "working" },
  { name: "ruff", version: ">=0.6.0", category: "Testing", purpose: "Lint + format", status: "working" },
  { name: "httpx2", version: ">=1.0", category: "Testing", purpose: "requirements-dev.txt's exact pin, needed by starlette.testclient.TestClient in tests/integration/test_api.py", status: "partial" },
  { name: "next", version: "16.3.0", category: "Frontend", purpose: "This dashboard's app framework", status: "working" },
  { name: "react / react-dom", version: "19.2.8", category: "Frontend", purpose: "UI library", status: "working" },
  { name: "typescript", version: "^5", category: "Frontend", purpose: "Type checking", status: "working" },
  { name: "tailwindcss", version: "^4", category: "Frontend", purpose: "Styling", status: "working" },
  { name: "reactflow", version: "^11.11.4", category: "Frontend", purpose: "Architecture diagram rendering", status: "working" },
  { name: "recharts", version: "^3.10.1", category: "Frontend", purpose: "Charts", status: "working" },
];

export const envVars: EnvVar[] = [
  { name: "DATABASE_URL", category: "Database", used: true, referenceCount: 2, file: "core/memory_store/store.py:init_db, api/main.py:85" },
  { name: "GOVERNEDMEMORY_API_KEYS", category: "Authentication", used: true, referenceCount: 1, file: "api/auth.py:31" },
  { name: "GOVERNEDMEMORY_OPERATION_SECRET", category: "Authentication", used: true, referenceCount: 2, file: "core/memory_store/store.py:534,632" },
  { name: "GOVERNEDMEMORY_EXTERNAL_WRITE_CLAIM_TTL_SECONDS", category: "Backend", used: true, referenceCount: 1, file: "core/memory_store/store.py:623" },
  { name: "INJECTION_THRESHOLD", category: "AI", used: true, referenceCount: 2, file: "core/detection/scanner.py:56, core/governance/service.py:37" },
  { name: "SEVERE_INJECTION_THRESHOLD", category: "AI", used: true, referenceCount: 1, file: "core/governance/service.py:42 — used in code, not documented in deploy/.env.example" },
  { name: "OPENAI_API_KEY", category: "AI", used: true, referenceCount: 1, file: "api/main.py:65" },
  { name: "OPENAI_EMBEDDING_MODEL", category: "AI", used: true, referenceCount: 1, file: "api/main.py:71" },
  { name: "EMBEDDING_DIM", category: "AI", used: true, referenceCount: 1, file: "api/main.py:69" },
  { name: "COHERE_API_KEY", category: "AI", used: false, referenceCount: 1, file: "core/memory_store/embeddings.py:195 — CohereEmbeddingProvider exists but api/main.py's fallback chain never selects it" },
  { name: "EMBEDDING_MODEL", category: "AI", used: false, referenceCount: 0, file: "documented in deploy/.env.example, but SentenceTransformerProvider() is called with no args in api/main.py:78 — this var is currently dead" },
  { name: "GOVERNEDMEMORY_API_URL", category: "Frontend", used: true, referenceCount: 2, file: "web/lib/backend.ts:26, src/lib/backend.ts (this dashboard)" },
  { name: "GOVERNEDMEMORY_API_KEY", category: "Frontend", used: true, referenceCount: 2, file: "web/lib/backend.ts:27, src/lib/backend.ts (this dashboard)" },
];

export const apiKeys: ApiKeyItem[] = [
  {
    name: "GOVERNEDMEMORY_API_KEYS (server)",
    documented: true,
    used: true,
    file: "api/auth.py:27-40 — comma-separated tenant_id:key pairs, parsed fresh from env on every request, no DB table",
  },
  {
    name: "GOVERNEDMEMORY_API_KEY (client)",
    documented: true,
    used: true,
    file: "web/lib/backend.ts, src/lib/backend.ts — one tenant's key, read server-side only, sent as `Authorization: Bearer <key>`",
  },
  { name: "OPENAI_API_KEY", documented: true, used: true, file: "read implicitly by the openai SDK, api/main.py:65" },
  { name: "COHERE_API_KEY", documented: true, used: false, file: "core/memory_store/embeddings.py:195 — provider exists, unreachable via the API server's auto-selection" },
];

// apiRoutes is intentionally not hardcoded: the API Routes page fetches
// this list live from the backend's own /openapi.json (see
// src/app/api-routes/page.tsx), so it can never drift from api/main.py.
// This constant stays as the type-level shape reference / build-time
// fallback used when no backend is configured.
export const apiRoutes: ApiRoute[] = [];

export const notMountedRoutes: { path: string; note: string }[] = [
  {
    path: "core/policy_engine (get_policy / upsert_policy / check_privilege)",
    note: "MemoryStore methods exist but have no REST route yet — see web/README.md's 'Known gaps'",
  },
  {
    path: "core/audit/verifier.py:verify_chain",
    note: "Audit hash-chain verification exists but isn't exposed via any route",
  },
];

export const authMechanisms: AuthMechanism[] = [
  {
    name: "Per-tenant Bearer API key",
    file: "api/auth.py:24-56",
    status: "working",
    note: "HTTPBearer, require_tenant() resolves tenant_id from GOVERNEDMEMORY_API_KEYS; tenant_id is never accepted from the client body (api/schemas.py deliberately omits it)",
  },
  {
    name: "External-write operation secret",
    file: "core/memory_store/store.py:534,632",
    status: "working",
    note: "GOVERNEDMEMORY_OPERATION_SECRET gates the /v1/external-memories/* claim/bind flow",
  },
  { name: "User accounts / sign-up", file: "—", status: "missing", note: "No accounts table, no password/session handling anywhere in api/ or core/" },
  { name: "JWT / end-user sessions", file: "—", status: "missing", note: "Not present — auth is a single static key per deployment, by design ('self-host, zero extra infra')" },
  {
    name: "Sign-up UI",
    file: "web/app/signup/page.tsx:72-75",
    status: "partial",
    note: "Explicit TODO comment: UI-only stub, fakes success after a setTimeout, waiting on a real account-creation endpoint that doesn't exist yet",
  },
];

export const paymentFlow: PaymentStep[] = [];

export const paymentProviders: { name: string; status: "working" | "partial" | "missing"; note: string }[] = [
  { name: "Square", status: "missing", note: "Not present anywhere in this repository (grepped .py/.ts/.md, zero real hits)." },
  { name: "Stripe", status: "missing", note: "Not present anywhere in this repository." },
  { name: "PayPal", status: "missing", note: "Not present anywhere in this repository." },
];

export const cloudServices: CloudService[] = [
  { provider: "Postgres + pgvector", purpose: "Primary datastore — pgvector/pgvector:pg16 image in deploy/docker-compose.yml, or any managed Postgres (AWS RDS/GCP Cloud SQL/Azure/Supabase examples in deploy/.env.example)", status: "working" },
  { provider: "OpenAI API", purpose: "Optional embedding provider (see AI Analysis)", status: "working" },
  { provider: "Cohere API", purpose: "Provider class implemented, not reachable from the API server's fallback chain", status: "partial" },
  { provider: "AWS / Azure / GCP compute", purpose: "No provider-specific deploy config beyond the DB connection-string examples", status: "missing" },
];

export const observability = {
  provider: "none",
  status: "missing" as const,
  note: "No tracing/metrics library (OpenTelemetry etc.) is declared in any requirements-*.txt or imported anywhere in api/ or core/.",
};

export const externalSdks = [
  { name: "OpenAI", status: "working" as const, note: "Embeddings only (see AI Analysis) — not used for chat/completions" },
  { name: "Mem0", status: "working" as const, note: "sdk/python/metaworkers/adapters/mem0.py — external-write governance wrapper around Mem0 OSS, pinned to mem0ai==2.0.12" },
  { name: "Cohere", status: "partial" as const, note: "CohereEmbeddingProvider implemented (core/memory_store/embeddings.py:178) but not wired into api/main.py's auto-selection" },
];

export const promptTemplates: PromptTemplate[] = [];

export const agentFrameworkFlow: AgentFrameworkStep[] = [
  { label: "External write candidate", detail: "An agent framework (e.g. via the Mem0 adapter) proposes a memory write" },
  { label: "evaluate-write / evaluate-candidates", detail: "POST /v1/external-memories/evaluate-write(s) — core/governance evaluates purpose + provenance" },
  { label: "Injection scan", detail: "core/write_governor + core/detection score the content before it's trusted" },
  { label: "Bind or quarantine", detail: "POST /v1/external-memories/bind commits it; quarantine routes isolate untrusted content" },
  { label: "Governed retrieval", detail: "Later reads go through core/retrieval_engine + core/policy_engine's purpose-binding gate" },
];

export const workers: Worker[] = [];

export const agentFrameworkNote =
  "GovernedMemory isn't itself an agent — it has no LangChain/CrewAI/LlamaIndex/AutoGen dependency and no worker/task-queue concept. It's governed memory infrastructure that external agent frameworks write to and read from, via the REST API directly or through adapters like sdk/python/metaworkers/adapters/mem0.py. The 'Agent Framework' page here describes that role rather than an in-repo framework, since none exists.";

export const securityScore = 74;

export const securityFindings: SecurityFinding[] = [
  {
    id: "SEC-1",
    severity: "medium",
    title: "No rate limiting on any route",
    description: "No rate-limit middleware or dependency is present anywhere in api/main.py or its requirements, including the write and retrieve routes.",
    evidence: "No rate-limit middleware/library found in requirements-api.txt or api/main.py",
    file: "api/main.py",
    recommendation: "Add per-tenant request throttling ahead of write-heavy routes before production traffic.",
    status: "open",
  },
  {
    id: "SEC-2",
    severity: "medium",
    title: "No CORS configuration at all",
    description: "api/main.py registers no CORSMiddleware. In its current form the API is unusable directly from a browser on another origin, which also means there's no explicit, reviewable CORS policy to audit.",
    evidence: "grep for CORSMiddleware/add_middleware in api/ returns no matches",
    file: "api/main.py",
    recommendation: "If browser-direct calls are ever needed, add an explicit CORSMiddleware with a scoped allow-list rather than defaulting to none/wildcard.",
    status: "open",
  },
  {
    id: "SEC-3",
    severity: "low",
    title: "Single static API key per tenant, no rotation or revocation path",
    description: "GOVERNEDMEMORY_API_KEYS is a flat env var; rotating or revoking one tenant's key means editing and redeploying the env var for all tenants.",
    evidence: "api/auth.py:27-40 — key map parsed fresh from one env var, no per-key metadata or expiry",
    file: "api/auth.py",
    recommendation: "If multi-tenant self-hosting grows past a handful of tenants, consider per-key expiry/rotation without redeploying the whole map.",
    status: "open",
  },
  {
    id: "SEC-4",
    severity: "low",
    title: "EMBEDDING_MODEL env var is documented but dead",
    description: "deploy/.env.example documents EMBEDDING_MODEL for choosing a local sentence-transformers model, but api/main.py:_build_embedder calls SentenceTransformerProvider() with no arguments, so the env var has no effect.",
    evidence: "core/memory_store/embeddings.py:75 default parameter never receives an env-sourced override in api/main.py:75-79",
    file: "api/main.py",
    recommendation: "Either read EMBEDDING_MODEL when constructing SentenceTransformerProvider, or remove it from deploy/.env.example.",
    status: "open",
  },
];

export const securityClean: SecurityClean[] = [
  { title: "No hardcoded secrets found", file: "api/, core/, web/, sdk/" },
  { title: ".env correctly gitignored — only .env.example files tracked", file: ".gitignore" },
  { title: "No eval()/exec() usage anywhere in api/ or core/", file: "api/, core/" },
  { title: "tenant_id is never accepted from the client — always resolved server-side from the API key", file: "api/auth.py, api/schemas.py" },
  { title: "Audit log is hash-chained and append-only, with an (unrouted but implemented) chain verifier", file: "core/audit/verifier.py:76, core/memory_store/store.py:133" },
  { title: "Write-time prompt-injection scoring gates untrusted content before it's trusted at read time", file: "core/write_governor/, core/detection/" },
  { title: "OpenAI/Cohere API keys are read server-side only, via each SDK's own env lookup — never logged or returned in a response", file: "api/main.py:_build_embedder" },
];

export const severityCounts = { critical: 0, high: 0, medium: 2, low: 2 };

export const recommendations: Recommendation[] = [
  {
    id: "REC-1",
    priority: "medium",
    category: "Security",
    title: "Add rate limiting to write/retrieve routes",
    impact: "POST /v1/memory and /v1/retrieve are unprotected against abuse from a valid-but-misbehaving tenant key.",
    fix: "Add per-tenant throttling middleware/dependency ahead of these routes.",
    progress: "not started",
  },
  {
    id: "REC-2",
    priority: "low",
    category: "Configuration",
    title: "Fix or remove the dead EMBEDDING_MODEL env var",
    impact: "Operators following deploy/.env.example will set EMBEDDING_MODEL expecting it to change the local embedding model, and nothing will happen.",
    fix: "Thread the env var into SentenceTransformerProvider(model_name=...) in api/main.py:_build_embedder, or delete it from the example file.",
    progress: "not started",
  },
  {
    id: "REC-3",
    priority: "medium",
    category: "API surface",
    title: "Route core/policy_engine's policy management and core/audit's chain verifier",
    impact: "get_policy/upsert_policy/check_privilege and verify_chain are fully implemented on MemoryStore but unreachable over HTTP — every REST consumer (including this dashboard and web/) is missing that functionality.",
    fix: "Add GET/POST /v1/policy, POST /v1/check-privilege, and GET /v1/audit/verify routes mirroring the existing route patterns in api/main.py.",
    progress: "not started",
  },
  {
    id: "REC-4",
    priority: "low",
    category: "Auth",
    title: "Decide whether web/'s signup stub becomes real",
    impact: "web/app/signup/page.tsx exists and looks functional but silently no-ops — a real user could believe they created an account.",
    fix: "Either wire it to a real account-creation endpoint (a genuine scope change from this repo's current self-hosted, single-key-per-tenant model) or remove the page until that's decided.",
    progress: "not started",
  },
];

export const architectureNodes: ArchitectureNodeData[] = [
  { id: "web", label: "web/ console", sub: "Next.js, Server Components + Actions", kind: "frontend" },
  { id: "dashboard", label: "This dashboard", sub: "Next.js, live report pages", kind: "frontend" },
  { id: "api", label: "FastAPI (api/main.py)", sub: "20 routes, Bearer auth", kind: "backend" },
  { id: "governor", label: "write_governor + detection", sub: "dedup + injection scoring", kind: "worker" },
  { id: "embed", label: "Embedding provider", sub: "OpenAI → local → zero-vector", kind: "ai" },
  { id: "store", label: "MemoryStore", sub: "core/memory_store, raw psycopg2", kind: "backend" },
  { id: "retrieval", label: "retrieval_engine + policy_engine", sub: "fusion search + purpose-binding gate", kind: "worker" },
  { id: "audit", label: "audit chain", sub: "hash-chained, append-only", kind: "worker" },
  { id: "db", label: "Postgres + pgvector", sub: "memory / audit / policy / external_* tables", kind: "database" },
];

export const architectureEdges: ArchitectureEdge[] = [
  { source: "web", target: "api", animated: true },
  { source: "dashboard", target: "api", animated: true },
  { source: "api", target: "governor", animated: true },
  { source: "governor", target: "embed" },
  { source: "governor", target: "store", animated: true },
  { source: "api", target: "retrieval", animated: true },
  { source: "retrieval", target: "store" },
  { source: "store", target: "db", animated: true },
  { source: "store", target: "audit" },
  { source: "audit", target: "db" },
];

export const repoStats = {
  files: repoMeta.trackedFiles,
  directories: 42,
  linesOfCode: repoMeta.pythonLoc,
  routes: 20,
  packages: packages.length,
  promptFiles: promptTemplates.length,
  envVars: envVars.length,
  securityFindings: securityFindings.length,
  integrations: externalSdks.length,
  workers: workers.length,
};

export const statusColor: Record<string, string> = {
  working: "good",
  partial: "warn",
  missing: "crit",
};

export const kpis: KpiItem[] = [
  { label: "Repository", value: repoMeta.name, sub: repoMeta.branch },
  { label: "Commit", value: repoMeta.commit, sub: `${repoMeta.lastCommitDate}` },
  { label: "Tracked files", value: repoMeta.trackedFiles },
  { label: "Python LOC", value: "~21,297" },
  { label: "Embedding providers", value: aiProviders.length, sub: "fallback chain" },
  { label: "Backend framework", value: "FastAPI", sub: ">=0.115" },
  { label: "REST routes", value: 20 },
  { label: "Env variables", value: envVars.length },
  { label: "Security findings", value: securityFindings.length, sub: "0 critical" },
  { label: "Repository score", value: `${repoScore} / 100` },
];
