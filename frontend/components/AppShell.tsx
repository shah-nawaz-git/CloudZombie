"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useIdentity } from "@/lib/queries";
import { ModeBadge } from "./chips";
const navigation = [
  ["/", "Overview"],
  ["/findings", "Findings"],
  ["/scans", "Scans"],
  ["/settings", "Settings"],
  ["/about", "About"],
] as const;
export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const identity = useIdentity();
  const title =
    navigation.find(([route]) => (route === "/" ? path === route : path.startsWith(route)))?.[1] ||
    "CloudZombie";
  return (
    <>
      <aside className="sidebar">
        <div className="wordmark">CloudZombie</div>
        <nav className="nav">
          {navigation.map(([href, label]) => (
            <Link
              className={path === href || (href !== "/" && path.startsWith(href)) ? "active" : ""}
              href={href}
              key={href}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">Read-only analysis · no remediation API</div>
      </aside>
      <header className="topbar">
        <h1>{title}</h1>
        {identity.data ? (
          <ModeBadge identity={identity.data} />
        ) : (
          <span className="muted">Identity loading…</span>
        )}
      </header>
      <main className="main">{children}</main>
    </>
  );
}
