import type { RouteObject } from "react-router-dom";
import { BrandsPage } from "./pages/BrandsPage";
import { CompetitorsPage } from "./pages/CompetitorsPage";
import { DiagnosisPage } from "./pages/DiagnosisPage";
import { LoginPage } from "./pages/LoginPage";
import { NewStudyPage } from "./pages/NewStudyPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlanPage } from "./pages/PlanPage";
import { ProposalPage } from "./pages/ProposalPage";
import { RegisterPage } from "./pages/RegisterPage";
import { StudyIndex } from "./pages/StudyIndex";
import { StudyLayout } from "./pages/StudyLayout";
import { TrackingPage } from "./pages/TrackingPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/registro", element: <RegisterPage /> },
  { path: "/verificar", element: <VerifyEmailPage /> },
  { path: "/", element: <NewStudyPage /> },
  { path: "/marcas", element: <BrandsPage /> },
  { path: "/marcas/:brandId", element: <TrackingPage /> },
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
