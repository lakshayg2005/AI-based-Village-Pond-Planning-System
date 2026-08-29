const API_URL = "http://localhost:8000";

export async function contourLines(polygon,gridSize=30,contourInterval=10){
    const response=await fetch(`${API_URL}/api/contours/generate`, {
        method: "POST",
        headers: {  
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
            polygon:polygon,
            grid_size: gridSize,
            contour_interval: contourInterval
        }),
    });
if (!response.ok) {
    const error = await response.json();

    throw new Error(
        error.detail || "Failed to generate contour lines"
    );
}
    return await response.json();
       
}