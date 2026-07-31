import { FullScreenBrandLoader, type LoaderStep } from "./FullScreenBrandLoader";

export interface AuthTransitionLoaderProps {
  title: string;
  subtitle: string;
  steps?: LoaderStep[];
  error?: string | null;
  onRetry?: () => void;
  onReturnToLogin?: () => void;
  progress?: number | null;
}

export function AuthTransitionLoader({
  title,
  subtitle,
  steps,
  error,
  onRetry,
  onReturnToLogin,
  progress,
}: AuthTransitionLoaderProps) {
  return (
    <FullScreenBrandLoader
      title={title}
      subtitle={subtitle}
      steps={steps}
      error={error}
      onRetry={onRetry}
      secondaryAction={
        onReturnToLogin ? { label: "Return to sign in", onClick: onReturnToLogin } : undefined
      }
      progress={progress}
    />
  );
}
