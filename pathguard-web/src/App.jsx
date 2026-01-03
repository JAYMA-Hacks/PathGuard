import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router";
import Tabs from "./Tabs";
import Home from "./TabContent/Home";
import Radar from "./TabContent/Radar";


  const tabs_logged = [
            { id: "home", label: "Home", content: <Home/>},
            { id: "radar", label: "Radar", content: <Radar/>},
          ];
  const tabs_not_logged = [
            { id: "home", label: "Home", content: <Home/>},
            { id: "radar", label: "Radar", content: <Radar/>},
          ];

function App() {
  const logged_status = false;

  return (
  <Router>
    <div>
      <main style = {{ padding: "1rem 1rem" }}>
        <Tabs
          tabs ={logged_status ? tabs_logged : tabs_not_logged}></Tabs>
      </main>
      <Routes>
        <Route path = "/" element = {<Navigate to="/home"/>}/>
        <Route path = "/home" element={<Home />} />
        <Route path = "/radar" element = {<Radar />}/>
      </Routes>
    </div>
  </Router>
  );
}

export default App;
