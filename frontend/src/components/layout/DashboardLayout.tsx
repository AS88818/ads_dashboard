"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Megaphone, Target, Settings, Activity, Search, TrendingUp } from "lucide-react";
import React from "react";
import { UserButton } from "@clerk/nextjs";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const navigation = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Google Ads", href: "/google", icon: Target },
  { name: "Meta Ads", href: "/meta", icon: Megaphone },
  { name: "Recommendations", href: "/recommendations", icon: Activity },
  { name: "Outcome Tracking", href: "/tracking", icon: TrendingUp },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full w-65 flex-col bg-surface border-r border-border/50 z-10 py-6 px-4">
      
      {/* Logo */}
      <div className="flex items-center px-4 mb-8">
        <h1 className="text-lg font-black leading-tight text-accent-primary tracking-tight">YCK Ads Dashboard</h1>
      </div>



      <div className="flex flex-1 flex-col overflow-y-auto">
        <nav className="flex-1 space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "group flex items-center rounded-xl px-4 py-3 text-sm font-bold transition-all",
                  isActive 
                    ? "bg-accent-lime text-accent-primary" 
                    : "text-text-muted hover:bg-surface-hover hover:text-foreground"
                )}
              >
                <Icon className={cn(
                  "mr-3 h-5 w-5 shrink-0", 
                  isActive ? "text-accent-primary" : "text-text-muted group-hover:text-foreground"
                )} aria-hidden="true" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Profile Card (Bottom) */}
      <div className="mt-auto px-2 pt-4">
        <Link href="/settings" className="flex items-center justify-between w-full p-2 rounded-xl hover:bg-surface-hover transition-colors group">
          <div className="flex items-center gap-3">
            <UserButton />
            <div className="text-left overflow-hidden">
              <p className="text-sm font-bold text-foreground truncate group-hover:text-accent-primary transition-colors">Account Settings</p>
              <p className="text-[10px] font-medium text-text-muted truncate">Manage profile</p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}

export function Header() {
  return (
    <header className="flex h-20 shrink-0 items-center justify-between bg-background px-8">
      {/* Left: Search Bar */}
      <div className="flex items-center gap-4">
         <div className="relative w-72">
           <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
             <Search className="w-4 h-4 text-text-muted" />
           </div>
           <input type="text" placeholder="Search..." className="h-10 w-full rounded-full bg-surface border border-border/40 pl-9 pr-12 text-sm focus:outline-none focus:border-accent-primary shadow-sm" disabled />
           <div className="absolute inset-y-0 right-0 flex items-center pr-3 gap-1">
             <span className="text-[10px] font-bold text-text-muted">⌘</span>
             <span className="text-[10px] font-bold text-text-muted">K</span>
           </div>
         </div>
      </div>

      {/* Right: Account */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-3">
          <UserButton />
        </div>
      </div>
    </header>
  );
}

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden relative">
        <Header />
        <main className="flex-1 overflow-y-auto p-8 pt-0">
          <div className="max-w-350 mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
