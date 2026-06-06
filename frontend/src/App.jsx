import { useEffect, useState } from "react";
import { getConfig, getThemes, buildItinerary } from "./api.js";
import Onboarding from "./components/Onboarding.jsx";
import Itinerary from "./components/Itinerary.jsx";
import Player from "./components/Player.jsx";

export default function App() {
  const [screen, setScreen] = useState("onboarding"); // onboarding | itinerary | player
  const [config, setConfig] = useState({ hasTts: false });
  const [themes, setThemes] = useState([]);
  const [tour, setTour] = useState(null);
  const [activeStop, setActiveStop] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig().then(setConfig).catch(() => {});
    getThemes().then(setThemes).catch(() => setError("Could not load themes"));
  }, []);

  async function start(prefs) {
    setLoading(true);
    setError("");
    try {
      const result = await buildItinerary(prefs);
      setTour(result);
      setScreen("itinerary");
    } catch (e) {
      setError("Couldn't build your tour. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  function openStop(i) {
    setActiveStop(i);
    setScreen("player");
  }

  return (
    <div className="app">
      {screen === "onboarding" && (
        <Onboarding themes={themes} onStart={start} loading={loading} error={error} />
      )}
      {screen === "itinerary" && tour && (
        <Itinerary
          tour={tour}
          onOpen={openStop}
          onRestart={() => setScreen("onboarding")}
        />
      )}
      {screen === "player" && tour && (
        <Player
          stops={tour.stops}
          index={activeStop}
          setIndex={setActiveStop}
          hasTts={tour.meta?.hasTts}
          vibe={tour.meta?.vibe}
          onBack={() => setScreen("itinerary")}
        />
      )}
    </div>
  );
}
