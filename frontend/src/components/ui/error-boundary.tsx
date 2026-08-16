"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error in component tree:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="product-panel my-4 border border-red-500/20 bg-[linear-gradient(180deg,rgba(239,68,68,0.08),rgba(255,255,255,0.95))] p-4 text-center">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.15em] text-red-600">
              Section Unavailable
            </p>
            <p className="mt-1 font-sans text-[11px] leading-relaxed text-foreground/72">
              An error occurred while loading this section of your dashboard.
            </p>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
