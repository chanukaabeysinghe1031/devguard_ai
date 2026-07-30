import { useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, File as FileIcon, Trash2, UploadCloud } from "lucide-react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { startAnalysis } from "../../api/analysesApi";
import { ApiError } from "../../api/client";
import { uploadIncidentFiles } from "../../api/filesApi";
import { createIncident } from "../../api/incidentsApi";
import { listProjects } from "../../api/projectsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert } from "../../components/ui/Alert";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { Input } from "../../components/ui/Input";
import { LinkButton } from "../../components/ui/LinkButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import type { UploadedFile } from "../../types/file";
import { cn } from "../../utils/cn";
import { formatFileSize } from "../../utils/formatters";

const schema = z.object({
  project_id: z.string().min(1, "Select a project"),
  title: z.string().min(1, "Title is required").max(255),
  description: z.string().max(5000).optional().or(z.literal("")),
  severity: z.enum(["critical", "high", "medium", "low"]),
  environment: z.string().max(50).optional().or(z.literal("")),
  source: z.enum(["manual_upload", "manual", "webhook", "api"]),
});

type FormValues = z.infer<typeof schema>;

const SEVERITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const SOURCE_OPTIONS = [
  { value: "manual_upload", label: "Manual upload" },
  { value: "manual", label: "Manual entry" },
  { value: "webhook", label: "Webhook" },
  { value: "api", label: "API" },
];

const ENVIRONMENT_OPTIONS = [
  { value: "", label: "Not set" },
  { value: "production", label: "Production" },
  { value: "staging", label: "Staging" },
  { value: "development", label: "Development" },
];

const STEPS = ["Details", "Upload artifacts", "Review & start"] as const;

export function IncidentCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(0);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [incidentTitle, setIncidentTitle] = useState<string>("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [serverError, setServerError] = useState<string | null>(null);

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects({ page: 1, page_size: 100 }),
    queryFn: () => listProjects({ page: 1, page_size: 100 }),
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      project_id: searchParams.get("projectId") ?? "",
      severity: "medium",
      source: "manual_upload",
    },
  });

  const createMutation = useMutation({
    mutationFn: (values: FormValues) =>
      createIncident({
        project_id: values.project_id,
        title: values.title,
        description: values.description || null,
        severity: values.severity,
        environment: values.environment || null,
        source: values.source,
      }),
    onSuccess: (incident) => {
      setIncidentId(incident.id);
      setIncidentTitle(incident.title);
      setStep(1);
    },
    onError: (error) => {
      setServerError(error instanceof ApiError ? error.message : "Failed to create incident.");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => uploadIncidentFiles(incidentId!, pendingFiles),
    onSuccess: (response) => {
      setUploadedFiles(response.files);
      setPendingFiles([]);
      setStep(2);
    },
    onError: (error) => {
      setServerError(error instanceof ApiError ? error.message : "File upload failed.");
    },
  });

  const startMutation = useMutation({
    mutationFn: () =>
      startAnalysis(incidentId!, {
        analysis_type: "full",
        file_ids: uploadedFiles.map((file) => file.id),
        options: {
          enable_rag: true,
          enable_llm: true,
          generate_recommendations: true,
          execution_mode: "rag_llm",
          retrieval_mode: "embedding_only",
        },
      }),
    onSuccess: () => {
      navigate(`/incidents/${incidentId}/analysis`, { replace: true });
    },
    onError: (error) => {
      setServerError(error instanceof ApiError ? error.message : "Failed to start analysis.");
    },
  });

  const handleFilesSelected = (files: FileList | null) => {
    if (!files) return;
    setPendingFiles((prev) => [...prev, ...Array.from(files)]);
  };

  const removePendingFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const projectOptions = projectsQuery.data?.items.map((project) => ({ value: project.id, label: project.name })) ?? [];

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="New incident"
        breadcrumbs={<Breadcrumbs items={[{ label: "Incidents", to: "/incidents" }, { label: "New incident" }]} />}
        description="Create an incident and upload CI/CD artifacts to start an AI-powered analysis."
      />

      <div className="mb-6 flex items-center gap-2">
        {STEPS.map((label, index) => (
          <div key={label} className="flex flex-1 items-center gap-2">
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                index < step
                  ? "border-primary bg-primary text-white"
                  : index === step
                    ? "border-primary text-primary"
                    : "border-border-strong text-text-muted",
              )}
            >
              {index < step ? <Check className="h-4 w-4" /> : index + 1}
            </div>
            <span className={cn("text-sm", index === step ? "text-text-primary" : "text-text-muted")}>{label}</span>
            {index < STEPS.length - 1 && <div className="h-px flex-1 bg-border-strong" />}
          </div>
        ))}
      </div>

      {serverError && (
        <Alert variant="danger" className="mb-4">
          {serverError}
        </Alert>
      )}

      {step === 0 && (
        <Card>
          <CardBody>
            {projectOptions.length === 0 && !projectsQuery.isLoading ? (
              <EmptyState
                title="Create a project first"
                description="You need at least one project before you can create an incident."
                action={<LinkButton to="/projects/new">Create project</LinkButton>}
              />
            ) : (
              <form
                onSubmit={handleSubmit((values) => {
                  setServerError(null);
                  createMutation.mutate(values);
                })}
                noValidate
                className="flex flex-col gap-4"
              >
                <Select
                  label="Project"
                  required
                  placeholder="Select a project"
                  options={projectOptions}
                  error={errors.project_id?.message}
                  {...register("project_id")}
                />
                <Input label="Title" required error={errors.title?.message} {...register("title")} />
                <Textarea label="Description" error={errors.description?.message} {...register("description")} />
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Select
                    label="Severity"
                    required
                    options={SEVERITY_OPTIONS}
                    error={errors.severity?.message}
                    {...register("severity")}
                  />
                  <Select label="Environment" options={ENVIRONMENT_OPTIONS} {...register("environment")} />
                </div>
                <Select label="Source" required options={SOURCE_OPTIONS} {...register("source")} />
                <div className="mt-2 flex justify-end">
                  <Button type="submit" isLoading={createMutation.isPending}>
                    Continue
                  </Button>
                </div>
              </form>
            )}
          </CardBody>
        </Card>
      )}

      {step === 1 && incidentId && (
        <Card>
          <CardBody>
            <p className="mb-3 text-sm text-text-secondary">
              Upload GitHub Actions logs, workflow YAML, or Terraform files for <strong>{incidentTitle}</strong>.
            </p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex w-full flex-col items-center gap-2 rounded-lg border border-dashed border-border-strong bg-surface-interactive/50 px-6 py-10 text-center transition-colors hover:border-primary hover:bg-surface-hover"
            >
              <UploadCloud className="h-8 w-8 text-text-muted" />
              <span className="text-sm font-medium text-text-primary">Click to select files</span>
              <span className="text-xs text-text-muted">.log, .yml, .yaml, .tf, .tfvars, .json, .txt</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(event) => handleFilesSelected(event.target.files)}
              accept=".log,.yml,.yaml,.tf,.tfvars,.json,.txt"
            />

            {pendingFiles.length > 0 && (
              <ul className="mt-4 flex flex-col gap-2">
                {pendingFiles.map((file, index) => (
                  <li
                    key={`${file.name}-${index}`}
                    className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface-interactive px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2 truncate">
                      <FileIcon className="h-4 w-4 shrink-0 text-text-muted" />
                      <span className="truncate text-text-primary">{file.name}</span>
                      <span className="shrink-0 text-xs text-text-muted">{formatFileSize(file.size)}</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => removePendingFile(index)}
                      aria-label={`Remove ${file.name}`}
                      className="text-text-muted hover:text-danger"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-6 flex justify-between">
              <Button type="button" variant="ghost" onClick={() => setStep(0)}>
                Back
              </Button>
              <Button
                type="button"
                disabled={pendingFiles.length === 0}
                isLoading={uploadMutation.isPending}
                onClick={() => {
                  setServerError(null);
                  uploadMutation.mutate();
                }}
              >
                Upload &amp; continue
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {step === 2 && incidentId && (
        <Card>
          <CardBody>
            <p className="text-sm text-text-secondary">
              Ready to analyse <strong>{incidentTitle}</strong> with {uploadedFiles.length} file
              {uploadedFiles.length === 1 ? "" : "s"}.
            </p>
            <ul className="mt-3 flex flex-col gap-1.5">
              {uploadedFiles.map((file) => (
                <li key={file.id} className="flex items-center gap-2 text-sm text-text-secondary">
                  <FileIcon className="h-4 w-4 text-text-muted" />
                  {file.original_filename}
                </li>
              ))}
            </ul>
            <div className="mt-6 flex justify-between">
              <Button type="button" variant="ghost" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                type="button"
                isLoading={startMutation.isPending}
                onClick={() => {
                  setServerError(null);
                  startMutation.mutate();
                }}
              >
                Start analysis
              </Button>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
