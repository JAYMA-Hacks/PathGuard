import "./Home.css";

export default function Home() {
    return (
      <div className = "home">
<header className="hero">
  <h1>City-wide safety management.</h1>
  <p className="tagline special">
    Smart crosswalks powered by AI + community input. Detect people, trigger lights,
    tag hazards, and show them on a public map.
  </p>

  <div className="actions tagline">
    <a href="/radar" className="btn primary">View Radar</a>
  </div>
</header>

{/* Features */}
<section className="features tagline">
  <h2>Features</h2>
  <p>
    <strong>See &amp; Act:</strong> Camera detects pedestrians and turns the light on automatically.
  </p>
  <p>
    <strong>Count &amp; Learn:</strong> Counts foot traffic to plan better timing.
  </p>
  <p>
    <strong>Report &amp; Share:</strong> Tag hazards on-site
  </p>
</section>
 
      </div>
    );
}