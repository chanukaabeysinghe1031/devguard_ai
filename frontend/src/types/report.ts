export interface ReportGenerateRequest {
  format?: string;
  include_evidence?: boolean;
  include_recommendations?: boolean;
  include_timeline?: boolean;
  include_resolution?: boolean;
}

export interface ReportGenerateResponse {
  report_id: string;
  incident_id: string;
  format: string;
  generation_status: string;
}

export interface ReportListItem {
  id: string;
  incident_id: string;
  incident_number: string;
  incident_title: string;
  format: string;
  version: number;
  generation_status: string;
  created_at: string;
  generated_by: string | null;
}

export interface ReportDetail {
  id: string;
  incident_id: string;
  format: string;
  version: number;
  generation_status: string;
  created_at: string;
  generated_by: string | null;
  download_url: string;
  content: Record<string, unknown> | null;
}
