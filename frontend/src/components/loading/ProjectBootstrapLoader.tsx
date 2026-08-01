import { FullScreenBrandLoader, type LoaderStep } from "./FullScreenBrandLoader";

export interface ProjectBootstrapLoaderProps {
  projectName?: string;
  steps?: LoaderStep[];
  error?: string | null;
  onRetry?: () => void;
  onBackToProjects?: () => void;
  progress?: number | null;
}

export function ProjectBootstrapLoader({
  projectName,
  steps,
  error,
  onRetry,
  onBackToProjects,
  progress,
}: ProjectBootstrapLoaderProps) {
  return (
    <FullScreenBrandLoader
      projectName={projectName}
      title="Loading project"
      steps={steps}
      stepsMode="status"
      error={error}
      onRetry={onRetry}
      secondaryAction={
        onBackToProjects ? { label: "Return to projects", onClick: onBackToProjects } : undefined
      }
      progress={progress}
    />
  );
}
