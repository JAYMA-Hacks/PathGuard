import MapView from '../api/MapView';
import './Radar.css';
const hazards_icons = ['pothole','icy','flood','fallen_sign','debris'];
const hazards_desc = ['Potholes','Icy Conditions','Flood Warning','Fallen Sign','Debris or Construction'];
const congest_icons = ['low','med','high'];
const congest_desc = ['Low Congestion','Medium Congestion','High Congestion'];
export default function Radar() {
    return (
        <div>
            <MapView/> {/**Map view display */}
            <div className = 'legend'> {/**Legend display */}
                {congest_icons.map((id,i) => (
                    <p key={i} className = 'legend-text'>
                        <img
                            src = {require(`../assets/congestion/${id}.png`)}
                            width = "30"
                        />
                        <span>{congest_desc[i]}</span>
                    </p>
                ))}
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
