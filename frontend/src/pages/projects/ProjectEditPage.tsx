import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { ApiError } from "../../api/client";
import { getProject, updateProject } from "../../api/projectsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert, ErrorRetryAlert } from "../../components/ui/Alert";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { PageHeader } from "../../components/ui/PageHeader";
import { Select } from "../../components/ui/Select";
import { Skeleton } from "../../components/ui/Skeleton";
import { Textarea } from "../../components/ui/Textarea";

const schema = z.object({
  description: z.string().max(2000).optional().or(z.literal("")),
  repository_url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
  default_branch: z.string().max(120).optional().or(z.literal("")),
  cloud_provider: z.string().max(50).optional().or(z.literal("")),
  default_environment: z.string().max(50).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

const CLOUD_OPTIONS = [
  { value: "", label: "None" },
  { value: "aws", label: "AWS" },
  { value: "gcp", label: "GCP" },
  { value: "azure", label: "Azure" },
  { value: "other", label: "Other" },
];

const ENVIRONMENT_OPTIONS = [
  { value: "", label: "Not set" },
  { value: "production", label: "Production" },
  { value: "staging", label: "Staging" },
  { value: "development", label: "Development" },
];

export function ProjectEditPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const projectQuery = useQuery({
    queryKey: queryKeys.project(projectId ?? ""),
    queryFn: () => getProject(projectId!),
    enabled: Boolean(projectId),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (projectQuery.data) {
      reset({
        description: projectQuery.data.description ?? "",
        repository_url: projectQuery.data.repository_url ?? "",
        default_branch: projectQuery.data.default_branch ?? "",
        cloud_provider: projectQuery.data.cloud_provider ?? "",
        default_environment: projectQuery.data.default_environment ?? "",
      });
    }
  }, [projectQuery.data, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      updateProject(projectId!, {
        description: values.description || null,
        repository_url: values.repository_url || null,
        default_branch: values.default_branch || null,
        cloud_provider: values.cloud_provider || null,
        default_environment: values.default_environment || null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId ?? "") });
      navigate(`/projects/${projectId}`);
    },
  });

  if (projectQuery.isLoading) {
    return <Skeleton className="h-64 w-full max-w-2xl" />;
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorRetryAlert message="Failed to load project." onRetry={() => projectQuery.refetch()} />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title={`Edit ${projectQuery.data.name}`}
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: "Projects", to: "/projects" },
              { label: projectQuery.data.name, to: `/projects/${projectId}` },
              { label: "Edit" },
            ]}
          />
        }
      />

      {mutation.isError && (
        <Alert variant="danger" className="mb-4">
          {mutation.error instanceof ApiError ? mutation.error.message : "Failed to update project."}
        </Alert>
      )}

      <Card>
        <CardBody>
          <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate className="flex flex-col gap-4">
            <Textarea label="Description" error={errors.description?.message} {...register("description")} />
            <Input
              label="Repository URL"
              error={errors.repository_url?.message}
              {...register("repository_url")}
            />
            <Input label="Default branch" error={errors.default_branch?.message} {...register("default_branch")} />
            <Select label="Cloud provider" options={CLOUD_OPTIONS} {...register("cloud_provider")} />
            <Select label="Default environment" options={ENVIRONMENT_OPTIONS} {...register("default_environment")} />
            <div className="mt-2 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => navigate(`/projects/${projectId}`)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={mutation.isPending}>
                Save changes
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
