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
          <div className="border border-red-500/20 bg-red-500/5 p-4 rounded text-center my-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-red-600 font-semibold">
              Section Unavailable
            </p>
            <p className="font-sans text-[11px] text-muted-foreground mt-1">
              An error occurred while loading this section of your dashboard.
            </p>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
