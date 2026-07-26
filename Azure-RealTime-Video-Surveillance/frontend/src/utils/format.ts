/** "laptop-webcam" -> "Laptop Webcam", "nest-front-door" -> "Nest Front Door". */
export function formatCameraLabel(cameraId: string): string {
  return cameraId
    .split(/[-_]/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
