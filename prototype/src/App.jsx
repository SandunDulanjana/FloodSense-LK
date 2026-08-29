import { HashRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import RiskTicker from "./components/RiskTicker";
import OverviewView from "./views/OverviewView";
import M1View from "./views/M1View";
import M2View from "./views/M2View";
import M3View from "./views/M3View";
import M4View from "./views/M4View";

export default function App() {
  return (
    <HashRouter>
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <RiskTicker />
        <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
          <Sidebar />
          <main style={{ flex: 1, padding: "24px 28px", overflowY: "auto" }}>
            <Routes>
              <Route path="/" element={<OverviewView />} />
              <Route path="/m1" element={<M1View />} />
              <Route path="/m2" element={<M2View />} />
              <Route path="/m3" element={<M3View />} />
              <Route path="/m4" element={<M4View />} />
            </Routes>
          </main>
        </div>
      </div>
    </HashRouter>
  );
}
