"use client";

import * as React from "react";
import { EvidenceViewerModal } from "./evidence-viewer-modal";

export interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  chunkId: string | null;
  documentId?: string | null;
  citationLabel?: string | null;
  evidenceText?: string | null;
  page?: number | null;
  section?: string | null;
  documentTitle?: string | null;
  score?: number | null;
  rank?: number | null;
  totalCandidates?: number | null;
}

/**
 * EvidenceDrawer delegates directly to EvidenceViewerModal,
 * providing the rich split-screen document & scoring inspector.
 */
export function EvidenceDrawer(props: EvidenceDrawerProps) {
  return <EvidenceViewerModal {...props} />;
}
