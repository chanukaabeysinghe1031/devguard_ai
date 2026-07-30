import { GitBranch, GitCommitHorizontal, Github, Workflow } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getPipelineRun } from "../../../api/pipelineRunsApi";
import { queryKeys } from "../../../api/queryKeys";
import { Badge } from "../../../components/ui/Badge";
import { Card, CardBody } from "../../../components/ui/Card";
import { Skeleton } from "../../../components/ui/Skeleton";
import { isSafeGitHubUrl } from "../../../utils/githubUrl";

/** Shows GitHub Actions context (workflow, branch, commit) when the incident originated from a connected pipeline run. */
export function GitHubContextCard({ pipelineRunId }: { pipelineRunId: string | null }) {
  const runQuery = useQuery({
    queryKey: queryKeys.pipelineRun(pipelineRunId ?? ""),
    queryFn: () => getPipelineRun(pipelineRunId!),
    enabled: Boolean(pipelineRunId),
  });

  if (!pipelineRunId) return null;
  if (runQuery.isLoading) return <Skeleton className="mb-6 h-16 w-full" />;
  if (runQuery.isError || !runQuery.data || runQuery.data.provider !== "github_actions") return null;

  const run = runQuery.data;
  const showLink = isSafeGitHubUrl(run.source_url);
  const shortSha = run.commit_sha ? run.commit_sha.slice(0, 7) : null;

  return (
    <Card className="mb-6">
      <CardBody className="flex flex-wrap items-center gap-x-6 gap-y-2 !py-3">
        <Badge tone="neutral">
          <Github className="h-3 w-3" /> GitHub Actions
        </Badge>
        {run.workflow_name && (
          <span className="flex items-center gap-1.5 text-sm text-text-secondary">
            <Workflow className="h-3.5 w-3.5 text-text-muted" /> {run.workflow_name}
          </span>
        )}
        {run.branch && (
          <span className="flex items-center gap-1.5 text-sm text-text-secondary">
            <GitBranch className="h-3.5 w-3.5 text-text-muted" /> {run.branch}
          </span>
        )}
        {shortSha && (
          <span className="flex items-center gap-1.5 font-mono text-sm text-text-secondary">
            <GitCommitHorizontal className="h-3.5 w-3.5 text-text-muted" /> {shortSha}
          </span>
        )}
        {showLink && run.source_url && (
          <a
            href={run.source_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-sm text-primary hover:underline"
          >
            View run on GitHub
          </a>
        )}
      </CardBody>
    </Card>
  );
}
