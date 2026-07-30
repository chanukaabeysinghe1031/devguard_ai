import { type ClassValue, clsx } from "clsx";

/** Merge conditional class names. Thin wrapper so call sites have one import. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
