import type { MapResearchResult } from "../../api/edit";

export interface AssignmentEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  researchResult: MapResearchResult;
}

export function AssignmentEditor(_props: AssignmentEditorProps) {
  return null; // RED — implementation in Task 2
}
