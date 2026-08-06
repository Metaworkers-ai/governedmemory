import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  FileText,
  Sparkles,
  Server,
  MonitorSmartphone,
  Package,
  KeyRound,
  Fingerprint,
  Route,
  ShieldCheck,
  CreditCard,
  Cloud,
  MessagesSquare,
  Workflow,
  ShieldAlert,
  Network,
  ListChecks,
  BarChart3,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    title: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/executive-summary", label: "Executive Summary", icon: FileText },
      { href: "/statistics", label: "Repository Statistics", icon: BarChart3 },
    ],
  },
  {
    title: "Engineering",
    items: [
      { href: "/ai-analysis", label: "AI Analysis", icon: Sparkles },
      { href: "/backend", label: "Backend", icon: Server },
      { href: "/frontend", label: "Frontend", icon: MonitorSmartphone },
      { href: "/packages", label: "Packages", icon: Package },
      { href: "/api-routes", label: "API Routes", icon: Route },
      { href: "/architecture", label: "Architecture", icon: Network },
    ],
  },
  {
    title: "Trust & Config",
    items: [
      { href: "/environment-variables", label: "Environment Variables", icon: KeyRound },
      { href: "/api-keys", label: "API Keys", icon: Fingerprint },
      { href: "/authentication", label: "Authentication", icon: ShieldCheck },
      { href: "/payments", label: "Payments", icon: CreditCard },
      { href: "/cloud-services", label: "Cloud Services", icon: Cloud },
    ],
  },
  {
    title: "AI Systems",
    items: [
      { href: "/prompt-templates", label: "Prompt Templates", icon: MessagesSquare },
      { href: "/agent-framework", label: "Agent Framework", icon: Workflow },
    ],
  },
  {
    title: "Assurance",
    items: [
      { href: "/security", label: "Security Audit", icon: ShieldAlert },
      { href: "/recommendations", label: "Recommendations", icon: ListChecks },
    ],
  },
];
