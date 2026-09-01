function CandidateList({
  candidates = [],
  selectedRank,
  onSelect,
}) {
  if (!candidates.length) {
    return (
      <div className="candidate-empty">
        No suitable pond candidates
        were found.
      </div>
    );
  }

  return (
    <div className="candidate-list">

      <div className="candidate-list-header">
        <div>
          <span className="eyebrow">
            SITES
          </span>

          <h2>
            Pond Candidates
          </h2>
        </div>

        <span className="candidate-count">
          {candidates.length}
        </span>
      </div>

      {candidates.map((candidate) => {
        const selected =
          Number(selectedRank) ===
          Number(candidate.rank);

        return (
          <button
            key={candidate.rank}
            type="button"
            className={`candidate-card ${
              selected
                ? "candidate-card-selected"
                : ""
            }`}
            onClick={() =>
              onSelect(candidate)
            }
          >

            {/* =========================================
                RANK
                ========================================= */}

            <div className="candidate-rank">
              {candidate.rank === 1
                ? "⭐"
                : `#${candidate.rank}`}
            </div>

            <div className="candidate-content">

              {/* =======================================
                  TOP
                  ======================================= */}

              <div className="candidate-top">

                <strong>
                  Candidate #
                  {candidate.rank}
                </strong>

                <span className="candidate-score">
                  {candidate.score != null
                    ? `${(
                        candidate.score * 100
                      ).toFixed(1)}%`
                    : "—"}
                </span>

              </div>

              {/* =======================================
                  COORDINATES
                  ======================================= */}

              <div className="candidate-coordinates">
                {candidate.latitude != null &&
                candidate.longitude != null
                  ? `${candidate.latitude.toFixed(
                      6
                    )}, ${candidate.longitude.toFixed(
                      6
                    )}`
                  : "Coordinates unavailable"}
              </div>

              {/* =======================================
                  V1 CANDIDATE STATS
                  ======================================= */}

              <div className="candidate-stats">

                <span>
                  Elevation{" "}
                  <strong>
                    {candidate.elevation_m != null
                      ? `${candidate.elevation_m.toFixed(
                          1
                        )} m`
                      : "—"}
                  </strong>
                </span>

                <span>
                  Slope{" "}
                  <strong>
                    {candidate.slope_percent != null
                      ? `${candidate.slope_percent.toFixed(
                          2
                        )}%`
                      : "—"}
                  </strong>
                </span>

                <span>
                  Flow{" "}
                  <strong>
                    {candidate.flow_accumulation != null
                      ? candidate.flow_accumulation.toLocaleString()
                      : "—"}
                  </strong>
                </span>

              </div>

              {/* =======================================
                  CATCHMENT
                  ======================================= */}

              <div className="candidate-stats">

                <span>
                  Catchment{" "}
                  <strong>
                    {candidate.catchment_area_hectares != null
                      ? `${candidate.catchment_area_hectares.toFixed(
                          2
                        )} ha`
                      : candidate.catchment_area_m2 != null
                      ? `${Math.round(
                          candidate.catchment_area_m2
                        ).toLocaleString()} m²`
                      : "—"}
                  </strong>
                </span>

              </div>

            </div>
          </button>
        );
      })}
    </div>
  );
}

export default CandidateList;