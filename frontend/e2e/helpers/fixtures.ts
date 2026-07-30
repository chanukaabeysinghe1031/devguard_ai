import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Sample diagnosis logs shipped in the repo (see `samples/diagnosis_logs/`). */
const SAMPLES_DIR = path.resolve(__dirname, "../../../samples/diagnosis_logs");

export const SAMPLE_LOGS = {
  mavenDependencyFailure: path.join(SAMPLES_DIR, "maven_dependency_failure.log"),
  awsAccessDenied: path.join(SAMPLES_DIR, "aws_access_denied.log"),
  terraformUndeclaredResource: path.join(SAMPLES_DIR, "terraform_undeclared_resource.log"),
  githubActionsRunnerOffline: path.join(SAMPLES_DIR, "github_actions_runner_offline.log"),
} as const;

for (const [name, filePath] of Object.entries(SAMPLE_LOGS)) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing sample diagnosis log fixture "${name}" at ${filePath}`);
  }
}

/** Static negative-test fixtures committed under `frontend/e2e/fixtures/`. */
const FIXTURES_DIR = path.resolve(__dirname, "../fixtures");

/** A zero-byte file with a supported extension — should be rejected as empty, not as unsupported type. */
export const EMPTY_FILE_PATH = path.join(FIXTURES_DIR, "empty.log");

/** An executable-extension file — should be rejected as an unsupported file type. */
export const UNSUPPORTED_FILE_PATH = path.join(FIXTURES_DIR, "unsupported.exe");

/** Backend MAX_UPLOAD_SIZE_BYTES default (see `.env`); generate a file just over this limit. */
const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024;
const OVERSIZED_FILE_SIZE_BYTES = MAX_UPLOAD_SIZE_BYTES + 1024 * 1024;
const OVERSIZED_FILE_PATH = path.join(os.tmpdir(), "devguard-e2e-oversized-fixture.log");

/**
 * Lazily generates an oversized (~11 MB) log fixture in the OS temp dir rather than committing a
 * large binary to the repository. Idempotent across repeated calls within a run.
 */
export function getOversizedFilePath(): string {
  const needsWrite =
    !fs.existsSync(OVERSIZED_FILE_PATH) || fs.statSync(OVERSIZED_FILE_PATH).size !== OVERSIZED_FILE_SIZE_BYTES;
  if (needsWrite) {
    fs.writeFileSync(OVERSIZED_FILE_PATH, Buffer.alloc(OVERSIZED_FILE_SIZE_BYTES, "a"));
  }
  return OVERSIZED_FILE_PATH;
}
