import { useOutletContext } from "react-router-dom";
import type { StudyStatus } from "../types/api";

export interface StudyContext {
  id: string;
  status: StudyStatus;
}

/** Estudio cargado por `StudyLayout` (con sondeo) para las pantallas hijas. */
export function useStudyContext() {
  return useOutletContext<StudyContext>();
}
