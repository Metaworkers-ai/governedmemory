export type Status = "working" | "partial" | "missing";

export interface RepoMeta {
  name: string;
  owner: string;
  branch: string;
  commit: string;
  clonedDate: string;
  lastCommitDate: string;
  trackedFiles: number;
  pythonLoc: number;
  backendStack: string;
  frontendStack: string;
}

export interface KpiItem {
  label: string;
  value: string | number;
  sub?: string;
  status?: Status;
}

export interface AiProvider {
  provider: string;
  sdk: string;
  model: string;
  file: string;
  purpose: string;
  referenceCount: number;
}

export interface BackendModule {
  name: string;
  path: string;
  role: string;
  status: Status;
  description: string;
  dependsOn?: string[];
}

export interface FrontendInfo {
  framework: string;
  version: string;
  routing: string;
  pages: { path: string; purpose: string }[];
  components: string[];
  configFiles: string[];
  note: string;
}

export interface PackageItem {
  name: string;
  version: string;
  category: "Backend" | "Frontend" | "AI" | "Database" | "Utilities" | "Testing" | "Monitoring" | "External SDK";
  purpose: string;
  status: Status;
}

export interface EnvVar {
  name: string;
  category: "AI" | "Database" | "Payments" | "Authentication" | "Backend" | "Frontend" | "External SDK" | "Monitoring";
  used: boolean;
  referenceCount: number;
  file?: string;
}

export interface ApiKeyItem {
  name: string;
  documented: boolean;
  used: boolean;
  file: string;
}

export interface ApiRoute {
  method: "GET" | "POST" | "PUT" | "DELETE";
  route: string;
  module: string;
  purpose: string;
  authRequired: boolean;
  status: Status;
  description: string;
  request?: string;
  response?: string;
  dependencies?: string[];
}

export interface AuthMechanism {
  name: string;
  file: string;
  status: Status;
  note: string;
}

export interface PaymentStep {
  label: string;
  status: Status;
  detail: string;
}

export interface CloudService {
  provider: string;
  purpose: string;
  status: Status;
}

export interface PromptTemplate {
  file: string;
  purpose: string;
  usedBy: string;
  model: string;
  intents?: string[];
}

export interface AgentFrameworkStep {
  label: string;
  detail: string;
}

export interface Worker {
  name: string;
  description: string;
  file: string;
}

export type Severity = "critical" | "high" | "medium" | "low";

export interface SecurityFinding {
  id: string;
  severity: Severity;
  title: string;
  description: string;
  evidence: string;
  file: string;
  recommendation: string;
  status: "open" | "resolved";
}

export interface SecurityClean {
  title: string;
  file: string;
}

export interface Recommendation {
  id: string;
  priority: "high" | "medium" | "low";
  category: string;
  title: string;
  impact: string;
  fix: string;
  progress: "not started" | "in progress" | "done";
}

export interface ArchitectureNodeData {
  id: string;
  label: string;
  sub: string;
  kind: "frontend" | "backend" | "ai" | "queue" | "worker" | "connector" | "payment" | "messaging" | "database";
}

export interface ArchitectureEdge {
  source: string;
  target: string;
  animated?: boolean;
  dashed?: boolean;
}
