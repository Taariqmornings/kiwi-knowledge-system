import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            padding: 40,
            color: "var(--text-muted)",
          }}>
            <div style={{ fontSize: "2rem", marginBottom: 16 }}>⚠</div>
            <h3 style={{ margin: "0 0 8px", color: "var(--text-title)" }}>Something went wrong</h3>
            <p style={{ fontSize: "0.85rem", maxWidth: 400, textAlign: "center" }}>
              {this.state.error?.message ?? "An unexpected error occurred."}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="btn btn-primary"
              style={{ marginTop: 16 }}
            >
              Try Again
            </button>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
