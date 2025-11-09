import MapView from '../api/MapView';
import './Radar.css';
const hazards_icons = ['pothole','icy','flood','fallen_sign','debris'];
const hazards_desc = ['Potholes','Icy Conditions','Flood Warning','Fallen Sign','Debris or Construction'];
export default function Radar() {
    return (
        <div>
            <MapView/> {/**Map view display */}
            <div className = 'legend'> {/**Legend display */}
                {hazards_icons.map((id,i) => (
                    <p key={i} className = 'legend-text'>
                        <img
                            src = {require(`../assets/hazards/${id}.png`)}
                            width = "30"
                        />
                        <span>{hazards_desc[i]}</span>
                    </p>
                ))}
            </div>
        </div>
    );
}
