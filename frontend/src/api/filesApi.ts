import { apiFetch } from "./client";
import type { FileDetail, UploadFilesResponse, UploadedFile } from "../types/file";

export async function uploadIncidentFiles(
  incidentId: string,
  files: File[],
  options: { fileCategory?: string; description?: string } = {},
): Promise<UploadFilesResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  if (options.fileCategory) form.append("file_category", options.fileCategory);
  if (options.description) form.append("description", options.description);
  return apiFetch<UploadFilesResponse>(`/incidents/${incidentId}/files`, {
    method: "POST",
    formData: form,
  });
}

export async function listIncidentFiles(incidentId: string): Promise<{ items: UploadedFile[] }> {
  return apiFetch<{ items: UploadedFile[] }>(`/incidents/${incidentId}/files`);
}

export async function getFile(fileId: string): Promise<FileDetail> {
  return apiFetch<FileDetail>(`/files/${fileId}`);
}

export async function deleteFile(fileId: string): Promise<void> {
  await apiFetch<void>(`/files/${fileId}`, { method: "DELETE" });
}
