import type { RouteObject } from "react-router-dom";
import { CompetitorsPage } from "./pages/CompetitorsPage";
import { DiagnosisPage } from "./pages/DiagnosisPage";
import { LoginPage } from "./pages/LoginPage";
import { NewStudyPage } from "./pages/NewStudyPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlanPage } from "./pages/PlanPage";
import { ProposalPage } from "./pages/ProposalPage";
import { StudyIndex } from "./pages/StudyIndex";
import { StudyLayout } from "./pages/StudyLayout";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/verificar", element: <VerifyEmailPage /> },
  { path: "/", element: <NewStudyPage /> },
  {
    path: "/studies/:id",
    element: <StudyLayout />,
    children: [
      { index: true, element: <StudyIndex /> },
      { path: "competidores", element: <CompetitorsPage /> },
      { path: "diagnostico", element: <DiagnosisPage /> },
      { path: "plan", element: <PlanPage /> },
      { path: "propuesta", element: <ProposalPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
];
