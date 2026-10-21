import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { nombres } from "../lib/study";
import { findingsFor, kitBrief, kitMarket, metricsFor, planFor, qualityFor, simulationFor } from "../mocks/data";
import * as db from "../mocks/db";
import { nb, renderUI } from "../test/utils";
import type { Action } from "../types/schemas";
import { ActionEditor } from "./ActionEditor";
import { FindingsList } from "./FindingsList";
import { RankingChart } from "./RankingChart";
import { ScoreCard } from "./ScoreCard";
import { VisibilityTables } from "./VisibilityTables";
import { PlanQualityCard } from "./PlanQualityCard";
import { SimulationCard } from "./SimulationCard";

const ID = "S-test";
const metrics = metricsFor(ID, kitMarket);
const findings = findingsFor(ID);
const nombre = nombres(kitMarket);

describe("ScoreCard", () => {
  it("muestra el score global, el puesto y el desglose 30/20/30/20", () => {
    renderUI(<ScoreCard metrics={metrics} nombre={nombre} />);
    expect(screen.getByTestId("score-global")).toHaveTextContent("25,93");
    expect(screen.getByText("8.ª de 10")).toBeInTheDocument();
    const filas = screen.getAllByRole("row").slice(1);
    expect(filas.map((f) => within(f).getByRole("rowheader").textContent)).toEqual([
      "Aparición 30",
      "Posición 20",
      "Fuerza 30",
      "Calidad de fuente 20",
    ]);
    // Los componentes suman el score.
    const suma = filas.reduce((s, f) => s + Number(within(f).getAllByRole("cell")[1].textContent!.replace(",", ".")), 0);
    expect(suma).toBeCloseTo(25.93, 2);
  });
});

describe("RankingChart", () => {
  it("ordena las marcas y marca la foco y la brecha con el líder", () => {
    renderUI(<RankingChart metrics={metrics} nombre={nombre} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(10);
    expect(items[0]).toHaveTextContent("Grupo Hospitalario Valdecruz66,46");
    expect(screen.getByTestId("ranking-foco")).toHaveTextContent("8.ªClínica Alborada Visión25,93");
    expect(screen.getByText(/Brecha con el líder: 40,53 pts/)).toBeInTheDocument();
  });
});

describe("VisibilityTables", () => {
  it("separa espontáneo y asistido por motor, fase y ciudad", async () => {
    const user = userEvent.setup();
    renderUI(<VisibilityTables metrics={metrics} ciudades={kitBrief.ciudades} nombreLider="Valdecruz" />);

    const claude = within(screen.getByTestId("visibilidad-motor")).getByRole("rowheader", { name: "Claude" })
      .parentElement!;
    const celdas = within(claude).getAllByRole("cell").map((c) => nb(c.textContent));
    expect(celdas[0]).toBe("15 %"); // espontáneo
    expect(celdas[4]).toBe("100 %"); // asistido, en su propia columna

    await user.click(screen.getByRole("tab", { name: "Ciudad" }));
    const bcn = within(screen.getByTestId("visibilidad-ciudad")).getByRole("rowheader", { name: "Barcelona" })
      .parentElement!;
    const c = within(bcn).getAllByRole("cell").map((x) => nb(x.textContent));
    expect(c[0]).toBe("4 %");
    expect(c[4]).toBe("—"); // sin preguntas asistidas por ciudad: guion, no 0 %

    await user.click(screen.getByRole("tab", { name: "Fase" }));
    expect(screen.getByRole("rowheader", { name: "Decisión" })).toBeInTheDocument();
  });
});

describe("FindingsList", () => {
  it("cada hallazgo muestra su cifra y abre sus evidencias con ids y texto", async () => {
    const id = db.crear("kit");
    const user = userEvent.setup();
    renderUI(<FindingsList studyId={id} findings={findingsFor(id)} marcas={kitMarket.marcas} />);

    const bcn = screen.getAllByTestId("hallazgo").find((h) => h.textContent!.includes("Barcelona"))!;
    expect(nb(bcn.textContent)).toContain("4 %");
    expect(bcn).toHaveTextContent("Confianza 65 %");
    await user.click(within(bcn).getByRole("button", { name: /Ver evidencias/ }));

    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getAllByTestId("evidencia").length).toBeGreaterThan(0));
    const primera = within(dialog).getAllByTestId("evidencia")[0];
    expect(primera).toHaveTextContent(findings.find((f) => f.id === "F-ciudad-barcelona")!.evaluation_ids[0]);
    expect(primera).toHaveTextContent(/Barcelona/);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("ActionEditor", () => {
  const plan = planFor(ID, metrics);
  const a4 = plan.fases[1].acciones.find((a) => a.id === "A4")!;

  function Harness() {
    const [a, setA] = useState<Action>(a4);
    return (
      <ActionEditor
        action={a}
        original={a4}
        findings={new Map(findings.map((f) => [f.id, f]))}
        restricciones={kitBrief.restricciones}
        readOnly={false}
        onChange={setA}
      />
    );
  }

  it("muestra los hallazgos que la justifican y marca la acción como editada", async () => {
    const user = userEvent.setup();
    renderUI(<Harness />);
    const just = screen.getAllByTestId("justificacion").map((j) => j.textContent);
    expect(just).toEqual([
      "37 resp.directoriomedico.example alimenta al líder y no a la marca",
      "1,01Aparece, pero casi nunca como recomendación",
    ]);
    expect(screen.queryByText("Editada")).not.toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Esfuerzo L" }));
    const resp = screen.getByLabelText("Responsable");
    await user.clear(resp);
    await user.type(resp, "Comunicación");
    expect(screen.getByText("Editada")).toBeInTheDocument();

    const sinRevisar = screen.getByRole("checkbox", { name: "Sin comparativas denigratorias" });
    expect(sinRevisar).not.toBeChecked();
    await user.click(sinRevisar);
    expect(sinRevisar).toBeChecked();
  });

  describe("SimulationCard", () => {
    it("muestra la proyección por fase, los rangos y los límites del modelo", () => {
      const plan = planFor(ID, metrics);
      renderUI(<SimulationCard simulation={simulationFor(ID, metrics, plan)} quality={qualityFor(ID, plan)} />);
      expect(screen.getByRole("heading", { name: "Proyección del plan" })).toBeInTheDocument();
      expect(screen.getByText("Base de entidad y medición")).toBeInTheDocument();
      expect(screen.getByText(/Estimación orientativa/)).toBeInTheDocument();
      expect(screen.getByText("Supuestos y límites de la estimación")).toBeInTheDocument();
    });
  });

  describe("PlanQualityCard", () => {
    it("marca las acciones que requieren revisión", () => {
      const plan = planFor(ID, metrics);
      renderUI(<PlanQualityCard quality={qualityFor(ID, plan)} />);
      expect(screen.getByText(/acciones A4/)).toBeInTheDocument();
      expect(screen.getByText("Restricciones")).toBeInTheDocument();
      expect(screen.getByText("86 %")).toBeInTheDocument();
    });
  });
});
