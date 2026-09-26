import { useState } from "react";
import { searchPlace } from "../services/api";

export default function PlaceSearch({ onSelect }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (!query.trim()) return;

    setBusy(true);
    setMessage("");
    try {
      const found = await searchPlace(query.trim());
      setResults(found);
      if (found.length === 0) setMessage("No places found");
    } catch {
      setResults([]);
      setMessage("Search is unavailable right now");
    } finally {
      setBusy(false);
    }
  };

  const choose = (place) => {
    onSelect(place.bounds);
    setResults([]);
    setQuery(place.name.split(",").slice(0, 2).join(","));
  };

  return (
    <form className="place-search" onSubmit={submit}>
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search a village, town or place…"
        aria-label="Search for a place"
      />
      <button type="submit" disabled={busy}>
        {busy ? "…" : "Go"}
      </button>

      {(results.length > 0 || message) && (
        <ul>
          {message && <li className="muted">{message}</li>}
          {results.map((place) => (
            <li key={place.name}>
              <button type="button" onClick={() => choose(place)}>
                {place.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
