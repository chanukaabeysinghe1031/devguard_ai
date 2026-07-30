import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check } from "lucide-react";
import { useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { createProject } from "../../api/projectsApi";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { PageHeader } from "../../components/ui/PageHeader";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { cn } from "../../utils/cn";

const schema = z.object({
  name: z.string().min(1, "Project name is required").max(150),
  key: z
    .string()
    .min(1, "Project key is required")
    .max(30)
    .regex(/^[A-Z0-9_-]+$/i, "Use letters, numbers, hyphens, or underscores only"),
  description: z.string().max(2000).optional().or(z.literal("")),
  repository_url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
  default_branch: z.string().max(120).optional().or(z.literal("")),
  ci_provider: z.enum(["github_actions", "gitlab", "jenkins", "other"]),
  cloud_provider: z.string().max(50).optional().or(z.literal("")),
  default_environment: z.string().max(50).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

const CI_OPTIONS = [
  { value: "github_actions", label: "GitHub Actions" },
  { value: "gitlab", label: "GitLab CI" },
  { value: "jenkins", label: "Jenkins" },
  { value: "other", label: "Other" },
];

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

const STEPS = ["Basics", "Repository", "Environment"] as const;

export function ProjectCreatePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    trigger,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ci_provider: "github_actions" },
  });

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      createProject({
        name: values.name,
        key: values.key.toUpperCase(),
        description: values.description || null,
        repository_url: values.repository_url || null,
        default_branch: values.default_branch || null,
        ci_provider: values.ci_provider,
        cloud_provider: values.cloud_provider || null,
        default_environment: values.default_environment || null,
      }),
    onSuccess: (project) => {
      navigate(`/projects/${project.id}`, { replace: true });
    },
    onError: (error) => {
      setServerError(error instanceof ApiError ? error.message : "Failed to create project.");
    },
  });

  const stepFields: Record<number, Array<keyof FormValues>> = {
    0: ["name", "key", "description"],
    1: ["repository_url", "default_branch", "ci_provider"],
    2: ["cloud_provider", "default_environment"],
  };

  const goNext = async () => {
    const valid = await trigger(stepFields[step]);
    if (valid) setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  const onSubmit = (values: FormValues) => {
    setServerError(null);
    mutation.mutate(values);
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="New project"
        breadcrumbs={<Breadcrumbs items={[{ label: "Projects", to: "/projects" }, { label: "New project" }]} />}
        description="Connect a repository so DevGuard AI can track pipeline runs and diagnose incidents."
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
            <span className={cn("text-sm", index === step ? "text-text-primary" : "text-text-muted")}>
              {label}
            </span>
            {index < STEPS.length - 1 && <div className="h-px flex-1 bg-border-strong" />}
          </div>
        ))}
      </div>

      {serverError && (
        <Alert variant="danger" className="mb-4">
          {serverError}
        </Alert>
      )}

      <Card>
        <CardBody>
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
            {step === 0 && (
              <>
                <Input label="Project name" required error={errors.name?.message} {...register("name")} />
                <Input
                  label="Project key"
                  required
                  hint="A short unique identifier, e.g. PAY for Payments."
                  error={errors.key?.message}
                  {...register("key")}
                />
                <Textarea label="Description" error={errors.description?.message} {...register("description")} />
              </>
            )}

            {step === 1 && (
              <>
                <Input
                  label="Repository URL"
                  placeholder="https://github.com/org/repo"
                  error={errors.repository_url?.message}
                  {...register("repository_url")}
                />
                <Input
                  label="Default branch"
                  placeholder="main"
                  error={errors.default_branch?.message}
                  {...register("default_branch")}
                />
                <Select
                  label="CI provider"
                  required
                  options={CI_OPTIONS}
                  error={errors.ci_provider?.message}
                  {...register("ci_provider")}
                />
              </>
            )}

            {step === 2 && (
              <>
                <Select label="Cloud provider" options={CLOUD_OPTIONS} {...register("cloud_provider")} />
                <Select
                  label="Default environment"
                  options={ENVIRONMENT_OPTIONS}
                  {...register("default_environment")}
                />
              </>
            )}

            <div className="mt-2 flex justify-between">
              <Button type="button" variant="ghost" onClick={goBack} disabled={step === 0}>
                Back
              </Button>
              {step < STEPS.length - 1 ? (
                <Button type="button" onClick={goNext}>
                  Continue
                </Button>
              ) : (
                <Button type="submit" isLoading={mutation.isPending}>
                  Create project
                </Button>
              )}
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
