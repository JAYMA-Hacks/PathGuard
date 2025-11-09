import { useEffect, useState } from "react";

export default function SimpleList() {
    consgt [rows, setRows] = useState([]);

    useEffect(() => {
        fetch("https://https://w9c3mxyrsc.execute-api.ca-west-1.amazonaws.com")
        .then(r => r.json())
        .then(setRows)
        .catch(console.error);
    }, []);
}