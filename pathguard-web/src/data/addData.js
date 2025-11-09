import fs from "fs";

const file = "./markers.json";
const markers = JSON.parse(fs.readFileSync(file,"utf8"));

const maxId = markers.length ? Math.max(...markers.map(m => m.id || 0)) : 0;

export default function addMarker({lng,lat,type,val}) {

    markers.push({id: maxId+1, lng: lng, lat: lat, type: type, val: val});
    fs.writeFileSync(file,JSON.stringify(markers,null,5));
    console.log(`Successfully added marker ${maxId+1}`);
}