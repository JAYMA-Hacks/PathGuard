import { useState, useCallback } from 'react';
import Map, {Marker, Popup, NavigationControl, GeolocateControl} from 'react-map-gl';
import MapboxGeocoder from "@mapbox/mapbox-gl-geocoder";
import mapboxgl from "mapbox-gl";
import { GrabData } from './AWSApi';


const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];

const TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

{/** Dictionary for hazard icons */}
function getImageURL(folder, name) {
    return new URL(`../assets/${folder}/${name}.png`, import.meta.url).href
}

function getImageURLsingle(name) {
    return new URL(`../assets/${name}.png`, import.meta.url).href
}

function truncateNumtoString(num) {
    const n_string = num.toString();

    const [integer,decimal] = n_string.split('.');

    if(!decimal) {
        return `${integer}.000000`;
    }

    const cleanDec = decimal.padEnd(6,'0').slice(0,6);

    return `${integer}.${cleanDec}`;
}

function getUniqueID(lng, lat) {
    return `${truncateNumtoString(lng)}${truncateNumtoString(lat)}`
}

export default function MapView() {
    const [markers, setMarkers] = useState([]);
    const [filters, setFilters] = useState({ hazard: true, congestion: true })
    const [popup, setPopup] = useState(null);
    const [selected, setSelected] = useState(null);
    const [cursorPos, setCursorPos] = useState(null);

    const { jsonData: marker_data, loading, error } = GrabData();

    const onMapClick = useCallback(e => {
        const {lng, lat} = e.lngLat;
        setMarkers(m => [...m,{lng,lat, hazard_id: null}]);
    }, []);

    

    if(loading) return <div>Loading...</div>;
    if(error) return <div style={{color: 'red'}}>Error: {error}</div>;
    const visible = marker_data.filter(m => filters[m.type]);
    
    if(marker_data)
        return (
        <div style={{height: '70vh', width: '100%', position: 'relative'}}>
            <div style ={{
                position: 'absolute', zIndex: 1, top: 50, left: 12,
                background: 'white', padding: 8, borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,.15)'
            }}>
                <label style = {{ display: 'block' }}>
                    <input
                        id = 'Hazard'
                        type = 'checkbox'
                        checked = {filters.hazard}
                        onChange = {e => setFilters(f => ({...f, hazard: e.target.checked}))}
                    />
                    Hazards
                </label>
                <label style = {{ display: 'block' }}>
                    <input
                        id = 'Congestion'
                        type = 'checkbox'
                        checked = {filters.congestion}
                        onChange = {e => setFilters(f => ({...f, congestion: e.target.checked}))}
                    />
                    Congestion
                </label>
            </div>
            <Map
            initialViewState={{longitude: -114.1345, latitude: 51.0788, zoom: 15}}
            mapStyle="mapbox://styles/mapbox/streets-v12"
            mapboxAccessToken={TOKEN}
            onClick={() => setSelected(null)}
            onMouseMove = {(e) => {
                const p = e.lngLat.wrap?.() ?? e.lngLat; // Keep lon within -180 -> 180
                setCursorPos({ lng: p.lng, lat: p.lat});
            }}
            onLoad={(ev) => {
                const map = ev.target;

                const geocoder = new MapboxGeocoder({
                    accessToken: TOKEN,
                    mapboxgl,
                    marker: false,
                    placeholder: "Search Area...",
                });

                map.addControl(geocoder,"bottom-right");

                geocoder.on("result",({ result }) => {
                    const [lng, lat] = result.center;
                    setMarkers((m) => [...m, { lng, lat }]);
                    setPopup({ lng, lat });
                    map.flyTo({ center: [lng, lat], zoom: 13 });
                });
            }}>
                <NavigationControl position="top-right" />
                <GeolocateControl position="top-left" />
                {visible.map((m) => (
                    <Marker key={getUniqueID(m.lng,m.lat)} longitude = {m.lng} latitude = {m.lat}>
                        <button type="button" style = {{background: 'none', border: 0, padding: 0, cursor: 'pointer'}} onClick = {(e) => {e.stopPropagation(); setSelected(m);}}><img
                            src = {m.type === 'hazard'
                            ? getImageURL('hazards',m.val)
                            : getImageURL('congestion',m.val)}
                            width = "50">
                        </img></button>
                    </Marker>
                ))}
                {selected && (
                    
                        <Popup
                    longitude={selected.lng}
                    latitude={selected.lat}
                    onClose={() => setSelected(null)}
                    closeOnClick = {false}
                    >
                        <strong>
                            CLASS: {selected.type} | {selected.val}
                        </strong>
                    </Popup>
                )}
            </Map>
            {cursorPos && (
                <div style={{
                    position: 'absolute', left: 9, bottom: 35, zIndex: 2,
                    padding: '6px 8px', background: 'rgba(0,0,0,0.6)', color: '#fff', borderRadius: 10, fontFamily: 'system-ui, sans-serif', fontSize: 12, pointerEvents: 'none'
                }}>
                    Longitude [{cursorPos.lng.toFixed(4)}] -- Latitude [{cursorPos.lat.toFixed(4)}]
                </div>
            )}
        </div>
    )
}