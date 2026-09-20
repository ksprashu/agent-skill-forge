# 🎨 Visual Production Guide: Mermaid Architecture Standards & Generative UI Simulators

Authoritative visual production guide for `/work` swarms, design architects, and verification auditors.
This document defines standard-compliant Mermaid diagram templates across primary software archetypes, Antigravity Generative UI standards for interactive "What-If" trade-off simulators, and a visual review quality checklist.

---

## 1. Universal Mermaid Syntax Invariants & Escaping Discipline

All Mermaid diagrams authored in `/work` design proposals (`proposal_alpha.md`, `proposal_beta.md`), authoritative designs (`DESIGN.md`), and task graphs (`DAG.md`) must adhere to strict escaping and formatting rules to prevent syntax crashes across markdown parsers and Antigravity preview panes.

### 1.1 Mandatory Node Quoting Invariant
Every node label containing spaces, hyphens, slashes, brackets `[]`, parentheses `()`, or punctuation **MUST** be enclosed in explicit double quotes:

```mermaid
%% CORRECT: Properly quoted node labels
flowchart TD
  node_a["API Gateway (FastAPI v0.110)"] --> node_b["Auth Worker [/auth/token]"]
```

```mermaid
%% INCORRECT: Unquoted parentheses or brackets break Mermaid parsing
flowchart TD
  node_a[API Gateway (FastAPI)] --> node_b[Auth Worker [/auth/token]]
```

### 1.2 Entity Escaping Matrix
When generating diagrams via scripts or LLM prompts, apply the following deterministic substitutions:

| Character / Token | Raw Syntax | Escaped Entity | Rationale |
|---|---|---|---|
| **Double Quote** | `"` | `#quot;` | Prevents premature string termination in node definitions |
| **Arrow Token** | `-->` / `==>` | `--&gt;` / `==&gt;` | Prevents Mermaid edge parser from misidentifying label text as edge syntax |
| **Pipe / Delimiter** | `\|` | `&#124;` | Avoids collision with Mermaid edge label syntax `\|label\|` |
| **Ampersand** | `&` | `&amp;` | Standard XML/HTML entity escaping |
| **Newline** | `\n` | `<br/>` | Formats multiline descriptions cleanly inside node boxes |
| **HTML Script Tags** | `<script>...</script>` | *STRIPPED* | Security invariant; prevents script injection |

### 1.3 Recommended Mermaid Class & Theme Palette
Use accessible, high-contrast dark/light palette classes for clear architectural layer distinctions:

```mermaid
classDef edge fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
classDef core fill:#0f172a,stroke:#6366f1,stroke-width:2px,color:#f8fafc;
classDef storage fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;
classDef queue fill:#701a75,stroke:#d946ef,stroke-width:2px,color:#fdf4ff;
classDef guard fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fef2f2;
```

---

## 2. Complete Diagram Templates by Software Archetype

### Archetype 1: Microservices Architecture

#### 1. System Architecture (`flowchart TD`)
```mermaid
flowchart TD
  subgraph EdgeTier ["Edge & Ingress Layer"]
    CLIENT["Client Applications<br/>(Web / Mobile / CLI)"]
    INGRESS["Ingress Reverse Proxy<br/>(Envoy / NGINX Gateway)"]
    AUTH_SVC["Auth & Token Service<br/>(OIDC / JWT Validator)"]
  end

  subgraph ServiceMesh ["Core Microservices Domain"]
    ORDER_SVC["Order Management Service<br/>(Go / gRPC Server)"]
    INVENTORY_SVC["Inventory Control Service<br/>(Rust / Tokio Engine)"]
    PAYMENT_SVC["Payment Processing Service<br/>(Python / FastAPI Worker)"]
    NOTIF_SVC["Notification Service<br/>(Node.js / WebSockets)"]
  end

  subgraph EventBus ["Event Streaming & Messaging"]
    KAFKA["Apache Kafka Broker<br/>(Topic: order-lifecycle)"]
    DLQ["Dead-Letter Queue<br/>(Topic: order-dlq)"]
  end

  subgraph StorageTier ["Distributed Persistence Tier"]
    ORDER_DB[("Order Primary DB<br/>[PostgreSQL 16 Cluster]")]
    INVENTORY_DB[("Inventory DB<br/>[Spanner / DynamoDB]")]
    CACHE_CLUSTER[("Distributed Cache<br/>[Redis Sentinel]")]
  end

  CLIENT --> INGRESS
  INGRESS --> AUTH_SVC
  INGRESS --> ORDER_SVC
  INGRESS --> INVENTORY_SVC

  ORDER_SVC --> CACHE_CLUSTER
  ORDER_SVC --> ORDER_DB
  ORDER_SVC --> KAFKA

  INVENTORY_SVC --> INVENTORY_DB
  INVENTORY_SVC -.->|Consume order-lifecycle| KAFKA

  KAFKA --> PAYMENT_SVC
  PAYMENT_SVC -.->|Publish result| KAFKA
  PAYMENT_SVC --> DLQ

  KAFKA --> NOTIF_SVC
  NOTIF_SVC --> CLIENT

  classDef edge fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
  classDef core fill:#0f172a,stroke:#6366f1,stroke-width:2px,color:#f8fafc;
  classDef storage fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;
  classDef queue fill:#701a75,stroke:#d946ef,stroke-width:2px,color:#fdf4ff;

  class CLIENT,INGRESS,AUTH_SVC edge;
  class ORDER_SVC,INVENTORY_SVC,PAYMENT_SVC,NOTIF_SVC core;
  class ORDER_DB,INVENTORY_DB,CACHE_CLUSTER storage;
  class KAFKA,DLQ queue;
```

#### 2. C4 Level 2/3 Component Block Diagram (`graph TD`)
```mermaid
graph TD
  subgraph OrderBoundary ["Container: Order Management Service [Go / gRPC]"]
    GRPCHandler["gRPC API Controller<br/>[Go Package: api/v1]<br/>Terminates RPC endpoints & validates payloads"]
    OrderManager["Order Domain Manager<br/>[Go Package: domain/order]<br/>Executes state machine & invariant checks"]
    SagaOrchestrator["Saga Coordinator<br/>[Go Package: orchestrator]<br/>Tracks distributed transactions & compensations"]
    KafkaProducer["Kafka Event Publisher<br/>[Go Package: infra/kafka]<br/>Publishes domain events with idempotent keys"]
    PostgresRepo["Postgres Repository Adapter<br/>[Go Package: infra/storage]<br/>Manages atomic transactions via pgx pool"]
  end

  subgraph ExternalDependencies ["External Subsystems & Infrastructure"]
    EnvoyProxy["Envoy Ingress Gateway"]
    PostgresStore[("PostgreSQL 16 Database")]
    KafkaCluster["Kafka Event Bus"]
    PaymentClient["Payment Service gRPC Client"]
  end

  EnvoyProxy --> GRPCHandler
  GRPCHandler --> OrderManager
  OrderManager --> SagaOrchestrator
  OrderManager --> PostgresRepo
  SagaOrchestrator --> KafkaProducer
  SagaOrchestrator --> PaymentClient
  PostgresRepo --> PostgresStore
  KafkaProducer --> KafkaCluster

  classDef component fill:#0f172a,stroke:#6366f1,stroke-width:2px,color:#f8fafc;
  classDef infra fill:#1e293b,stroke:#475569,stroke-width:2px,color:#f8fafc;
  class GRPCHandler,OrderManager,SagaOrchestrator,KafkaProducer,PostgresRepo component;
  class EnvoyProxy,PostgresStore,KafkaCluster,PaymentClient infra;
```

#### 3. Lifecycle Sequence Diagram (`sequenceDiagram`)
```mermaid
sequenceDiagram
  autonumber
  actor User as End User
  participant Gateway as API Gateway
  participant OrderSvc as Order Service
  participant Kafka as Kafka Event Broker
  participant PaymentSvc as Payment Service
  participant DB as Order Database

  User->>Gateway: POST /api/v1/orders (Create Order)
  Gateway->>OrderSvc: gRPC CreateOrder(payload)
  OrderSvc->>DB: BEGIN TX: Insert order (Status=PENDING)
  DB-->>OrderSvc: TX Committed (order_id=ord_9821)
  OrderSvc->>Kafka: Publish Event: OrderCreated(ord_9821)
  OrderSvc-->>Gateway: HTTP 202 Accepted (order_id=ord_9821)
  Gateway-->>User: Order Submitted Confirmation

  par Distributed Processing
    Kafka->>PaymentSvc: Consume OrderCreated(ord_9821)
    PaymentSvc->>PaymentSvc: Authorize & Charge Payment
    alt Payment Authorized
      PaymentSvc->>Kafka: Publish Event: PaymentSucceeded(ord_9821)
    else Payment Declined
      PaymentSvc->>Kafka: Publish Event: PaymentFailed(ord_9821, reason)
    end
  and Database Event Reconciliation
    Kafka->>OrderSvc: Consume PaymentSucceeded(ord_9821)
    OrderSvc->>DB: UPDATE orders SET status='CONFIRMED' WHERE id=ord_9821
    DB-->>OrderSvc: Status Updated
  end
```

---

### Archetype 2: CLI Engine Architecture

#### 1. System Architecture (`flowchart TD`)
```mermaid
flowchart TD
  subgraph ShellRuntime ["Shell & Terminal Surface"]
    INVOKE["Terminal Execution<br/>(pwsh / bash / zsh)"]
    ARGS["CLI Arguments & Flags<br/>(--config, --strict, --json)"]
  end

  subgraph CLICore ["CLI Application Kernel"]
    PARSER["Argument Parser & Normalizer<br/>(argparse / click / cobra)"]
    CONFIG["Configuration Resolver<br/>(File / Env / Flag Precedence)"]
    DISPATCH["Command Dispatcher & Router<br/>(Command Registry)"]
  end

  subgraph Subsystems ["Engine Subsystems"]
    WORKSPACE["Workspace Discovery & FS Inspector"]
    ENGINE["Core Business Logic / Pipeline Runner"]
    OUTPUT["Output Formatter<br/>(Human Rich Text / Structured JSON)"]
  end

  subgraph DiskSystem ["Host Environment"]
    FS[("Local Filesystem & Working Tree")]
    CACHE_DIR[("Global Cache (~/.config / AppData)")]
  end

  INVOKE --> ARGS
  ARGS --> PARSER
  PARSER --> CONFIG
  CONFIG --> DISPATCH
  DISPATCH --> WORKSPACE
  DISPATCH --> ENGINE
  WORKSPACE --> FS
  CONFIG --> CACHE_DIR
  ENGINE --> FS
  ENGINE --> OUTPUT
  OUTPUT --> INVOKE

  classDef cli fill:#1e293b,stroke:#475569,stroke-width:2px,color:#f8fafc;
  classDef core fill:#0f172a,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
  classDef disk fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;

  class INVOKE,ARGS cli;
  class PARSER,CONFIG,DISPATCH,WORKSPACE,ENGINE,OUTPUT core;
  class FS,CACHE_DIR disk;
```

#### 2. C4 Level 2/3 Component Block Diagram (`graph TD`)
```mermaid
graph TD
  subgraph CLIContainer ["Container: CLI Engine Binary"]
    Main["main.py Entrypoint<br/>[Python 3.12]<br/>Handles SIGINT, exit codes, UTF-8 wrapper"]
    ArgParser["CLI Argument Parser<br/>[Module: cli.parser]<br/>Parses flags, subcommands, and options"]
    ConfigLoader["Config Provider<br/>[Module: cli.config]<br/>Resolves config.json, env vars, defaults"]
    CommandRegistry["Command Router<br/>[Module: cli.router]<br/>Dispatches commands to registered handlers"]
    TaskRunner["Task Execution Engine<br/>[Module: core.engine]<br/>Coordinates pipeline jobs and concurrency"]
    Reporter["Result Formatter<br/>[Module: core.reporter]<br/>Renders ANSI colors, progress, and JSON"]
  end

  subgraph ExternalEnvironment ["Host Operating System"]
    StdinStdout["TTY / Stdio Streams"]
    LocalFS["Project Directory & Filesystem"]
    ProcessManager["OS Process Subsystem"]
  end

  StdinStdout --> Main
  Main --> ArgParser
  ArgParser --> ConfigLoader
  ConfigLoader --> CommandRegistry
  CommandRegistry --> TaskRunner
  TaskRunner --> LocalFS
  TaskRunner --> ProcessManager
  TaskRunner --> Reporter
  Reporter --> StdinStdout

  classDef comp fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
  classDef env fill:#334155,stroke:#64748b,stroke-width:2px,color:#f8fafc;
  class Main,ArgParser,ConfigLoader,CommandRegistry,TaskRunner,Reporter comp;
  class StdinStdout,LocalFS,ProcessManager env;
```

#### 3. Lifecycle Sequence Diagram (`sequenceDiagram`)
```mermaid
sequenceDiagram
  autonumber
  actor User as Terminal Operator
  participant Main as CLI Main Entrypoint
  participant Parser as Argument Parser
  participant Config as Config Provider
  participant Engine as Task Execution Engine
  participant FS as Local Filesystem

  User->>Main: Execute: agy run --strict --profile=ci
  Main->>Main: Apply UTF-8 wrapper & trap SIGINT
  Main->>Parser: Parse sys.argv flags
  Parser-->>Main: Parsed CommandOptions
  Main->>Config: Load configuration (--profile=ci)
  Config->>FS: Read project .agents/config.json
  FS-->>Config: Config data
  Config-->>Main: Merged RuntimeConfig
  Main->>Engine: RunPipeline(options, config)
  
  loop Staged Task Execution
    Engine->>FS: Inspect input artifacts
    Engine->>Engine: Execute task step
    Engine->>FS: Write output artifacts
  end

  alt Pipeline Succeeded
    Engine-->>Main: Success (all tasks passed)
    Main->>User: Output formatted summary (Exit Code 0)
  else Pipeline Failed
    Engine-->>Main: TaskFailure(task_id, error)
    Main->>User: Output error diagnostic (Exit Code 1)
  end
```

---

### Archetype 3: Pipeline / ETL Streaming Architecture

#### 1. System Architecture (`flowchart TD`)
```mermaid
flowchart TD
  subgraph Sources ["Upstream Data Ingestion"]
    S_API["REST / Webhook Ingestion API"]
    S_CDC["Database Change Data Capture (CDC)"]
    S_OBJECT["Cloud Storage Object Drops (GCS / S3)"]
  end

  subgraph IngestionBuffer ["Ingestion & Staging Queue"]
    BUFFER["High-Throughput Stream Buffer<br/>(Kafka / PubSub / Redis Streams)"]
    VALIDATOR["Ingestion Schema Validator<br/>(JSON Schema / Protobuf)"]
  end

  subgraph ProcessingEngine ["ETL Transformation Pipeline"]
    STAGE_CLEAN["Stage 1: Deduplication & Sanitization"]
    STAGE_ENRICH["Stage 2: Entity Enrichment & Join Engine"]
    STAGE_AGG["Stage 3: Windowed Aggregation & Rollups"]
    STAGE_DLQ["Dead-Letter Quarantine Handler"]
  end

  subgraph DestinationSinks ["Analytical Storage & Lakehouse"]
    WAREHOUSE[("Data Warehouse<br/>[BigQuery / Snowflake]")]
    LAKEHOUSE[("Parquet Lakehouse<br/>[Iceberg / Delta Tables]")]
    ALERT_SINK["Monitoring & Telemetry Sink"]
  end

  S_API --> BUFFER
  S_CDC --> BUFFER
  S_OBJECT --> BUFFER

  BUFFER --> VALIDATOR
  VALIDATOR -->|Valid Schema| STAGE_CLEAN
  VALIDATOR -->|Schema Mismatch| STAGE_DLQ

  STAGE_CLEAN --> STAGE_ENRICH
  STAGE_ENRICH --> STAGE_AGG

  STAGE_CLEAN -.->|Processing Failure| STAGE_DLQ
  STAGE_ENRICH -.->|Processing Failure| STAGE_DLQ

  STAGE_AGG --> WAREHOUSE
  STAGE_AGG --> LAKEHOUSE
  STAGE_DLQ --> ALERT_SINK

  classDef source fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
  classDef buffer fill:#312e81,stroke:#6366f1,stroke-width:2px,color:#e0e7ff;
  classDef stage fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
  classDef storage fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;

  class S_API,S_CDC,S_OBJECT source;
  class BUFFER,VALIDATOR buffer;
  class STAGE_CLEAN,STAGE_ENRICH,STAGE_AGG,STAGE_DLQ stage;
  class WAREHOUSE,LAKEHOUSE,ALERT_SINK storage;
```

#### 2. C4 Level 2/3 Component Block Diagram (`flowchart LR`)
```mermaid
flowchart LR
  subgraph IngestionBoundary ["Container: Stream Ingestion Worker"]
    Receiver["Event Ingestion Receiver<br/>[Python / FastStream]<br/>Consumes events from ingestion topic"]
    SchemaValidator["Schema Validation Filter<br/>[Pydantic v2 Models]<br/>Validates structure & field constraints"]
  end

  subgraph ProcessingBoundary ["Container: Transformation & Enrichment Engine"]
    Deduplicator["Stateful Deduplication Cache<br/>[Redis Bloom Filter]<br/>Prevents duplicate event processing"]
    Transformer["Feature Enrichment Transformer<br/>[Polars / PyArrow]<br/>Performs entity normalization & masking"]
    BatchAggregator["Micro-Batch Buffer<br/>[In-Memory Buffer]<br/>Batches records for bulk insertion"]
  end

  subgraph PersistenceBoundary ["Container: Analytical Storage Sink"]
    BigQueryWriter["BigQuery Storage Write Client<br/>[google-cloud-bigquery]<br/>Executes append writes with zero-copy"]
    DLQWriter["Dead-Letter Publisher<br/>[PubSub Client]<br/>Persists failed messages with error payload"]
  end

  Receiver --> SchemaValidator
  SchemaValidator -->|Schema Valid| Deduplicator
  SchemaValidator -->|Invalid| DLQWriter
  Deduplicator --> Transformer
  Transformer --> BatchAggregator
  BatchAggregator --> BigQueryWriter

  classDef comp fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
  class Receiver,SchemaValidator,Deduplicator,Transformer,BatchAggregator,BigQueryWriter,DLQWriter comp;
```

#### 3. Lifecycle Sequence Diagram (`sequenceDiagram`)
```mermaid
sequenceDiagram
  autonumber
  participant Stream as Message Stream
  participant Ingest as Ingestion Worker
  participant Cache as Deduplication Cache
  participant Transform as Enrichment Engine
  participant DW as Analytical Warehouse
  participant DLQ as Dead-Letter Queue

  Stream->>Ingest: Ingest Micro-Batch (1,000 records)
  Ingest->>Ingest: Validate JSON Schema
  
  alt Schema Validation Succeeded
    Ingest->>Cache: Query Bloom Filter (Check Event IDs)
    Cache-->>Ingest: Filter Result (12 duplicates detected)
    Ingest->>Transform: Forward 988 Unique Records
    Transform->>Transform: Apply Masking, Geo-Resolution & Metrics
    Transform->>DW: Bulk Append via Storage Write API
    DW-->>Transform: ACK: 988 records committed
    Transform-->>Ingest: Batch Complete
    Ingest->>Stream: Commit Stream Offset
  else Schema Validation Failed
    Ingest->>DLQ: Route Invalid Records with Error Metadata
    DLQ-->>Ingest: DLQ ACK
    Ingest->>Stream: Commit Stream Offset (Quarantined)
  end
```

---

### Archetype 4: Client-Server Web Architecture

#### 1. System Architecture (`flowchart TD`)
```mermaid
flowchart TD
  subgraph ClientApp ["Client Browser & Mobile UI"]
    BROWSER["Next.js / React Client App<br/>(SPA / SSR Frontend)"]
    STATE_STORE["Client State Store<br/>(TanStack Query / Zustand)"]
  end

  subgraph EdgeCloud ["Edge Network & CDN"]
    EDGE["Global CDN & WAF<br/>(Edge Cache / SSL Termination)"]
  end

  subgraph ServerApp ["Backend Web & Application Tier"]
    API["Application Gateway & Controllers<br/>(Node.js / Express / NestJS)"]
    SESSION["Session & Rate-Limit Store<br/>(Redis Cluster)"]
    BIZ["Domain Services & Business Logic"]
  end

  subgraph StorageTier ["Data Persistence Tier"]
    PRIMARY_DB[("Primary Relational Database<br/>[PostgreSQL with Replica Pool]")]
    S3_STORE[("Blob & Asset Storage<br/>[S3 / Cloud Storage]")]
  end

  BROWSER <--> STATE_STORE
  STATE_STORE <--> EDGE
  EDGE <--> API
  API <--> SESSION
  API <--> BIZ
  BIZ <--> PRIMARY_DB
  BIZ <--> S3_STORE

  classDef client fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
  classDef edge fill:#312e81,stroke:#6366f1,stroke-width:2px,color:#e0e7ff;
  classDef app fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
  classDef db fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;

  class BROWSER,STATE_STORE client;
  class EDGE edge;
  class API,SESSION,BIZ app;
  class PRIMARY_DB,S3_STORE db;
```

#### 2. C4 Level 2/3 Component Block Diagram (`graph TD`)
```mermaid
graph TD
  subgraph FrontendContainer ["Container: Web Frontend [React 19 / TypeScript]"]
    UIRoute["Page Routing & Layout<br/>[App Router]<br/>Handles URL routing & navigation"]
    QueryCache["Query & Mutation Manager<br/>[TanStack Query]<br/>Manages caching, retries, and optimistic updates"]
    AuthContext["Auth Context Provider<br/>[Context API]<br/>Manages JWT tokens and session refresh"]
  end

  subgraph BackendContainer ["Container: Backend Application [Node.js / Express]"]
    AuthMiddleware["Auth & Rate-Limit Middleware<br/>[Express Middleware]<br/>Verifies Bearer tokens & token buckets"]
    ResourceController["REST API Controllers<br/>[Routes Handler]<br/>Validates DTOs and handles requests"]
    DomainService["Domain Business Service<br/>[Service Layer]<br/>Enforces business logic and transactions"]
    ORMAdapter["Prisma / Drizzle ORM Adapter<br/>[Data Access Layer]<br/>Maps relational entities and queries"]
  end

  subgraph InfrastructureTier ["Database & External Services"]
    RedisSession["Redis Key-Value Cache"]
    PostgresDB[("PostgreSQL 16 Cluster")]
  end

  UIRoute --> QueryCache
  QueryCache --> AuthContext
  QueryCache --> AuthMiddleware
  AuthMiddleware --> RedisSession
  AuthMiddleware --> ResourceController
  ResourceController --> DomainService
  DomainService --> ORMAdapter
  ORMAdapter --> PostgresDB

  classDef fe fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
  classDef be fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
  classDef inf fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;
  class UIRoute,QueryCache,AuthContext fe;
  class AuthMiddleware,ResourceController,DomainService,ORMAdapter be;
  class RedisSession,PostgresDB inf;
```

#### 3. Lifecycle Sequence Diagram (`sequenceDiagram`)
```mermaid
sequenceDiagram
  autonumber
  actor User as End User
  participant UI as Web Frontend (React)
  participant API as Backend API
  participant Redis as Redis Cache
  participant DB as PostgreSQL Database

  User->>UI: Click "Update Profile"
  UI->>UI: Apply Optimistic UI Update
  UI->>API: PATCH /api/v1/users/me (Bearer Token)
  API->>Redis: Check Token Validity & Rate Limit
  Redis-->>API: Token Valid (Rate limit OK)
  API->>DB: UPDATE users SET name=..., bio=... WHERE id=user_123
  
  alt Database Update Succeeds
    DB-->>API: 1 row updated
    API->>Redis: Invalidate user_profile_cache:user_123
    API-->>UI: HTTP 200 OK (Updated User DTO)
    UI->>UI: Settle Optimistic State
    UI-->>User: Display Success Toast
  else Database Update Fails
    DB-->>API: Error: Constraint Violation
    API-->>UI: HTTP 400 Bad Request
    UI->>UI: Rollback Optimistic State
    UI-->>User: Display Error Banner
  end
```

---

## 3. Antigravity Generative UI Standards: "What-If" Simulators

When parallel design proposals reveal genuine architectural trade-offs, the Architectural Arbiter and Sentinel compile an interactive **What-If Architectural Trade-Off Simulator** (`.agents/design/what_if_simulator.html`).

### 3.1 Core Architecture & Sandboxing Invariants
1. **Self-Contained Single-File HTML5 Artifact**:
   - The entire simulator is packaged into a single HTML file containing HTML markup, scoped CSS styling, native JavaScript logic, and embedded JSON manifest state.
2. **Zero External CDN Dependencies (Strict CSP Audit)**:
   - Antigravity Generative UI artifacts execute in sandboxed iframes.
   - **PROHIBITED**: Unapproved external CDNs (`cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `unpkg.com`, external fonts, Chart.js, D3.js).
   - **PERMITTED**: Native HTML5 Canvas 2D, browser DOM APIs, and Google Antigravity approved local web runtime (`https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js` with pure CSS fallbacks).
3. **Headless & Non-JS Fallback Invariant**:
   - Every simulator artifact **MUST** include a `<noscript>` block containing a pre-rendered static HTML trade-off comparison matrix.
   - Automated CI scripts, test runners, and text-only agents can inspect all dimensions and profiles without evaluating JavaScript.

### 3.2 HTML5 Canvas 2D Retina Radar Engine
To achieve crisp rendering on high-DPI (Retina, 4K) displays with zero external graphing dependencies, radar charts are implemented using the HTML5 Canvas 2D API with explicit buffer scaling:

```javascript
/**
 * Vector-Grade Canvas 2D Radar Renderer with Retina Scaling
 */
function renderRadar(canvas, dimensions, values, benchmarkValues) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  // Scale internal buffer dimensions to match device pixel density
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const width = rect.width;
  const height = rect.height;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(centerX, centerY) - 40;
  const totalAxes = dimensions.length;

  ctx.clearRect(0, 0, width, height);

  // 1. Draw Concentric Polygonal Background Grids (20%, 40%, 60%, 80%, 100%)
  const levels = 5;
  for (let level = 1; level <= levels; level++) {
    const levelRadius = (radius / levels) * level;
    ctx.beginPath();
    for (let i = 0; i < totalAxes; i++) {
      const angle = (Math.PI * 2 / totalAxes) * i - Math.PI / 2;
      const x = centerX + levelRadius * Math.cos(angle);
      const y = centerY + levelRadius * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = "rgba(148, 163, 184, 0.15)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // 2. Draw Radial Axes & Axis Labels
  for (let i = 0; i < totalAxes; i++) {
    const angle = (Math.PI * 2 / totalAxes) * i - Math.PI / 2;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = "rgba(148, 163, 184, 0.25)";
    ctx.stroke();

    // Text Label Positioning
    const labelX = centerX + (radius + 22) * Math.cos(angle);
    const labelY = centerY + (radius + 18) * Math.sin(angle);
    ctx.fillStyle = "rgba(226, 232, 240, 0.85)";
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(dimensions[i].name, labelX, labelY);
  }

  // 3. Draw Polygon for Recommended Baseline (Emerald Fill)
  if (benchmarkValues) {
    drawPolygon(ctx, centerX, centerY, radius, dimensions, benchmarkValues, "rgba(16, 185, 129, 0.2)", "rgba(16, 185, 129, 0.8)", 1.5);
  }

  // 4. Draw Polygon for Active Configuration (Blue Fill)
  drawPolygon(ctx, centerX, centerY, radius, dimensions, values, "rgba(59, 130, 246, 0.35)", "rgba(59, 130, 246, 0.9)", 2.5);
}

function drawPolygon(ctx, centerX, centerY, radius, dimensions, values, fillColor, strokeColor, lineWidth) {
  const totalAxes = dimensions.length;
  ctx.beginPath();
  for (let i = 0; i < totalAxes; i++) {
    const dim = dimensions[i];
    const val = values[dim.id] !== undefined ? values[dim.id] : dim.defaultValue;
    // Normalize value to 0.0 .. 1.0 range
    const ratio = Math.max(0, Math.min(1, (val - dim.min) / (dim.max - dim.min)));
    const angle = (Math.PI * 2 / totalAxes) * i - Math.PI / 2;
    const x = centerX + radius * ratio * Math.cos(angle);
    const y = centerY + radius * ratio * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}
```

### 3.3 Markdown Choice-Card Clipboard Export
The simulator includes an export button that compiles user slider adjustments into a structured GitHub Flavored Markdown block ready for the Sentinel's `ask_question` tool:

```javascript
function exportDecisionMarkdown() {
  const profileName = state.profiles[state.activeProfileId]?.name || "Custom Configuration";
  let md = `### Architectural Decision Choice Card: ${profileName}\n\n`;
  md += `| Dimension | Selected Value | Target Range | Unit |\n`;
  md += `|---|---|---|---|\n`;
  for (const dim of state.dimensions) {
    const val = state.values[dim.id];
    md += `| **${dim.name}** | \`${val}\` | ${dim.min} – ${dim.max} | ${dim.unit} |\n`;
  }
  md += `\n**Composite System Score**: \`${calculateScore().toFixed(1)} / 100\`\n`;

  navigator.clipboard.writeText(md).then(() => {
    showExportConfirmation();
  });
}
```

---

## 4. Visual Production Quality Checklist

Before approving proposals, committing `DESIGN.md`, or passing Phase 7 verification, design reviewers and auditors must evaluate diagrams against this 10-point checklist:

### Syntax & Escaping Checklist
- [ ] **1. Quoting Invariant**: Are all Mermaid node labels containing spaces, brackets, parentheses, slashes, or hyphens enclosed in explicit double quotes (`id["Text"]`)?
- [ ] **2. Clean Entities**: Are internal quotes (`#quot;`), edge labels (`&#124;`), and arrow characters (`--&gt;`) properly escaped?
- [ ] **3. Direction & Type Directives**: Does every diagram begin with a standard directive (`flowchart TD`, `graph TD`, `sequenceDiagram`)?
- [ ] **4. Autonumber on Sequences**: Do all `sequenceDiagram` definitions specify `autonumber` on line 2 for traceability?

### Architectural Rigor Checklist
- [ ] **5. C4 Boundary Purity**: Do C4 component diagrams group elements inside subgraphs that represent authentic process or network boundaries (Containers / Services)?
- [ ] **6. Complete Archetype Representation**: Does the proposal contain all three mandatory visual views:
  - System Architecture Overview (`flowchart TD`)
  - C4 Component Block Diagram (`graph TD` / `flowchart LR`)
  - Lifecycle Sequence Diagram (`sequenceDiagram`)?
- [ ] **7. Parity with Declarative Contracts**: Do the component IDs in diagrams match the package, class, or service names defined in TypeScript/Python interface sections?

### Generative UI Simulator Checklist
- [ ] **8. Zero-CDN Sandboxing**: Does `what_if_simulator.html` run 100% offline without external CDN script tags (no unapproved Chart.js/D3/fonts)?
- [ ] **9. High-DPI Vector Crispness**: Does the radar canvas implement `window.devicePixelRatio` scaling so polygons render sharply on Retina screens?
- [ ] **10. Headless `<noscript>` Fallback**: Does the HTML file include a pre-rendered static comparison table inside `<noscript>` for headless testing environments?
