import { useNavigate, useLocation, Link } from "react-router-dom";
import { useState } from "react";
import './Tabs.css'
import logo from "./assets/PathGuard_Logo.png"



export default function Tabs({ tabs }) {
    const navigate = useNavigate();
    const location = useLocation();
    const active = location.pathname.split("/")[1] || tabs[0].id;

    function updateSite(id) {
        navigate(`/${id}`);
    }
    return (
        <div className = "tab">
            <div className = "group left">
                {tabs.map((t) => (
                    <button className = {`${active === t.id ? "active" : ""} ${active === "radar" ? "radar" : ""}`} key = {t.id} onClick = {() => updateSite(t.id)}>{t.label}</button>
                ))}
            </div>
            <div className = "group">
                <Link to="/home"> 
                    <img src = {logo} className = "logo"></img>
                </Link>
            </div>
        </div>
    )
}