import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EdaSection } from "../components/EdaSection";
import { StationarityCard } from "../components/StationarityCard";
import type { MovingAveragesResponse, SeasonalDecompositionResponse, StationarityResponse } from "../types";

export function EdaPage() {
  const [movingAverages, setMovingAverages] = useState<MovingAveragesResponse | null>(null);
  const [seasonalDecomposition, setSeasonalDecomposition] = useState<SeasonalDecompositionResponse | null>(
    null,
  );
  const [stationarity, setStationarity] = useState<StationarityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.movingAverages(), api.seasonalDecomposition(), api.stationarity()])
      .then(([ma, sd, st]) => {
        setMovingAverages(ma);
        setSeasonalDecomposition(sd);
        setStationarity(st);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load EDA data."));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Data &amp; Exploratory Analysis</h1>
      </div>

      {error && <div className="state-message error">{error}</div>}
      {!movingAverages && !error && <div className="state-message">Loading…</div>}

      {movingAverages && seasonalDecomposition && (
        <EdaSection movingAverages={movingAverages} seasonalDecomposition={seasonalDecomposition} />
      )}

      {stationarity && (
        <>
          <div className="section-title">Stationarity Tests</div>
          <StationarityCard stationarity={stationarity} />
        </>
      )}
    </div>
  );
}
