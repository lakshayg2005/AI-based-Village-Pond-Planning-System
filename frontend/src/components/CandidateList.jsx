function CandidateList({ candidates = [], selectedRank, onSelect }) {
    if (!candidates.length) {
      return (
        <div className="candidate-empty">
          No suitable pond candidates were found.
        </div>
      );
    }
  
    return (
      <div className="candidate-list">
        <div className="candidate-list-header">
          <div>
            <span className="eyebrow">SITES</span>
            <h2>Pond Candidates</h2>
          </div>
  
          <span className="candidate-count">
            {candidates.length}
          </span>
        </div>
  
        {candidates.map((candidate) => {
          const selected = selectedRank === candidate.rank;
  
          return (
            <button
              key={candidate.rank}
              className={`candidate-card ${
                selected ? "candidate-card-selected" : ""
              }`}
              onClick={() => onSelect(candidate)}
            >
              <div className="candidate-rank">
                {candidate.rank === 1
                  ? "⭐"
                  : `#${candidate.rank}`}
              </div>
  
              <div className="candidate-content">
                <div className="candidate-top">
                  <strong>
                    Candidate #{candidate.rank}
                  </strong>
  
                  <span className="candidate-score">
                    {(candidate.score * 100).toFixed(1)}%
                  </span>
                </div>
  
                <div className="candidate-coordinates">
                  {candidate.latitude.toFixed(6)},{" "}
                  {candidate.longitude.toFixed(6)}
                </div>
  
                <div className="candidate-stats">
                  <span>
                    Elevation{" "}
                    <strong>
                      {candidate.elevation_m.toFixed(1)} m
                    </strong>
                  </span>
  
                  <span>
                    Slope{" "}
                    <strong>
                      {candidate.slope_percent.toFixed(2)}%
                    </strong>
                  </span>
  
                  <span>
                    Flow{" "}
                    <strong>
                      {candidate.flow_accumulation}
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