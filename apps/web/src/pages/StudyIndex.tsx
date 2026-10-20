import { Navigate } from "react-router-dom";
import { pantallaActual } from "../lib/study";
import { useStudyContext } from "./studyContext";

/** `/studies/:id` lleva a la pantalla que toca según el estado del estudio. */
export function StudyIndex() {
  const { status } = useStudyContext();
  return <Navigate to={pantallaActual(status)} replace />;
}
