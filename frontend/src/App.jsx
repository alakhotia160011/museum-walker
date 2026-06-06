import { useEffect, useState } from "react";
import { getConfig, getThemes, buildItinerary } from "./api.js";
import Compose from "./components/Onboarding.jsx";
import Curating from "./components/Curating.jsx";
import Route from "./components/Itinerary.jsx";
import Stop from "./components/Player.jsx";

export default function App() {
  const [screen, setScreen] = useState("compose"); // compose | curating | route | stop
  const [config, setConfig] = useState({ hasTts: false, hasClaude: false });
  const [themes, setThemes] = useState([]);
  const [tour, setTour] = useState(null);
  const [activeStop, setActiveStop] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig().then(setConfig).catch(() => {});
    getThemes().then(setThemes).catch(() => setError("The themes couldn't be loaded."));
  }, []);

  async function compose(prefs) {
    setError("");
    setScreen("curating");
    const started = Date.now();
    try {
      const result = await buildItinerary(prefs);
      // let the curating transition breathe even when the route returns instantly
      const elapsed = Date.now() - started;
      if (elapsed < 1500) await new Promise((r) => setTimeout(r, 1500 - elapsed));
      setTour(result);
      setActiveStop(0);
      setScreen("route");
    } catch (e) {
      setError("The route couldn't be composed. Is the backend running?");
      setScreen("compose");
    }
  }

  function openStop(i) {
    setActiveStop(i);
    setScreen("stop");
    window.scrollTo(0, 0);
  }

  return (
    <div className="app">
      {screen === "compose" && (
        <Compose themes={themes} onCompose={compose} error={error} />
      )}
      {screen === "curating" && <Curating />}
      {screen === "route" && tour && (
        <Route tour={tour} onOpen={openStop} onRestart={() => setScreen("compose")} />
      )}
      {screen === "stop" && tour && (
        <Stop
          stops={tour.stops}
          index={activeStop}
          setIndex={(i) => { setActiveStop(i); window.scrollTo(0, 0); }}
          hasTts={tour.meta?.hasTts}
          hasClaude={config.hasClaude}
          vibe={tour.meta?.vibe}
          level={tour.meta?.level}
          themes={tour.meta?.themes}
          eras={tour.meta?.eras}
          next={tour.stops[activeStop + 1] || null}
          onBack={() => setScreen("route")}
        />
      )}
    </div>
  );
}
