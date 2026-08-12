import {
    APIProvider,
    Map,
    ControlPosition,
    MapControl,
    AdvancedMarker,
    useMap,
} from "@vis.gl/react-google-maps";

import { useEffect, useRef } from "react";

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const defaultCenter = {
    lat: 21.1904,
    lng: 81.2849,
};

function SearchBox() {
    const map = useMap();
    const containerRef = useRef(null);

    useEffect(() => {
        if (!map || !containerRef.current) return;

        const input = document.createElement("input");

        input.type = "text";
        input.placeholder = "Search for a place...";
        
        input.style.width = "350px";
        input.style.height = "45px";
        input.style.padding = "0 15px";
        input.style.fontSize = "16px";
        input.style.border = "none";
        input.style.borderRadius = "8px";
        input.style.boxShadow = "0 2px 6px rgba(0,0,0,0.3)";
        input.style.outline = "none";

        containerRef.current.appendChild(input);

        const autocomplete = new google.maps.places.Autocomplete(input);

        autocomplete.bindTo("bounds", map);

        autocomplete.addListener("place_changed", () => {
            const place = autocomplete.getPlace();

            if (!place.geometry || !place.geometry.location) {
                return;
            }

            if (place.geometry.viewport) {
                map.fitBounds(place.geometry.viewport);
            } else {
                map.setCenter(place.geometry.location);
                map.setZoom(15);
            }
        });

        return () => {
            input.remove();
        };
    }, [map]);

    return (
        <div
            ref={containerRef}
            style={{
                position: "absolute",
                top: "20px",
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 10,
            }}
        />
    );
}

function VillageMap() {
    return (
        <APIProvider
            apiKey={API_KEY}
            libraries={["places"]}
        >
            <div
                style={{
                    width: "100vw",
                    height: "100vh",
                    position: "relative",
                }}
            >
                <Map
                    defaultCenter={defaultCenter}
                    defaultZoom={12}
                    mapTypeControl={true}
                    fullscreenControl={true}
                    streetViewControl={true}
                    zoomControl={true}
                    gestureHandling="greedy"
                />

                <SearchBox />
            </div>
        </APIProvider>
    );
}

export default VillageMap;