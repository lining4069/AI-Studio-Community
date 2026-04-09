import { Bot, BrainCircuit, Database, Menu, Settings2 } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useUIStore } from "@/store/ui-store";
import { cn } from "@/lib/utils";
import type { NavItem } from "@/types";

const navItems: NavItem[] = [
  { label: "首页", to: "/home", icon: BrainCircuit },
  { label: "知识库", to: "/knowledge-bases", icon: Database },
  { label: "Agent", to: "/agents", icon: Bot },
  { label: "系统配置", to: "/settings", icon: Settings2 },
];

export function AppShell() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_30%),linear-gradient(180deg,_#f8fbff_0%,_#f6f7fb_100%)] text-slate-950">
      <div className="mx-auto flex min-h-screen max-w-[1680px] gap-4 p-4">
        <aside
          className={cn(
            "flex shrink-0 flex-col rounded-[2rem] border border-white/70 bg-white/80 p-4 shadow-xl shadow-slate-200/70 backdrop-blur-xl transition-all",
            sidebarCollapsed ? "w-24" : "w-72",
          )}
        >
          <div className="mb-6 flex items-center justify-between gap-3">
            <div className={cn("overflow-hidden", sidebarCollapsed && "sr-only")}>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">
                AI Studio
              </p>
              <h2 className="mt-1 text-lg font-semibold">桌面工作台</h2>
            </div>
            <Button variant="ghost" size="icon" onClick={toggleSidebar}>
              <Menu className="size-5" />
            </Button>
          </div>

          <nav className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium text-slate-600 transition",
                      isActive
                        ? "bg-slate-950 text-white shadow-lg shadow-slate-200"
                        : "hover:bg-slate-100",
                    )
                  }
                >
                  {Icon ? <Icon className="size-5 shrink-0" /> : null}
                  <span className={cn(sidebarCollapsed && "hidden")}>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-auto rounded-3xl bg-slate-950 p-4 text-white">
            <p className={cn("text-sm font-medium", sidebarCollapsed && "sr-only")}>
              浏览器优先，桌面就绪
            </p>
            <p
              className={cn(
                "mt-2 text-xs leading-5 text-slate-300",
                sidebarCollapsed && "sr-only",
              )}
            >
              当前壳子按 Tauri 2 打包预留，先专注把知识库、Agent 与设置工作流跑顺。
            </p>
          </div>
        </aside>

        <main className="flex min-h-[calc(100vh-2rem)] flex-1 flex-col rounded-[2rem] border border-white/70 bg-white/75 shadow-xl shadow-slate-200/70 backdrop-blur-xl">
          <div className="border-b border-slate-200/80 px-8 py-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">
                  AI Studio Workspace
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  面向知识库、Agent 与模型配置的一体化桌面工作台。
                </p>
              </div>
            </div>
          </div>
          <div className="flex-1 overflow-auto px-8 py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
