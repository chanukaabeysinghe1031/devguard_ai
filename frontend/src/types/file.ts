export interface UploadedFile {
  id: string;
  original_filename: string;
  file_type: string;
  size_bytes: number;
  checksum_sha256: string;
  validation_status: string;
  secret_masking_status: string;
  processing_status: string;
  uploaded_at: string | null;
  mime_type: string | null;
  incident_id: string | null;
  project_id: string | null;
  pipeline_run_id: string | null;
}

export interface UploadFilesResponse {
  files: UploadedFile[];
}

export interface FileDetail extends UploadedFile {
  extracted_metadata: Record<string, unknown> | null;
}
