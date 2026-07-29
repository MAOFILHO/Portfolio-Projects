import { useAlertSocket } from "../ws/useAlertSocket";
import { AlertFeed } from "./AlertFeed";
import { CaptureController } from "./CaptureController";
import { EventHistory } from "./EventHistory";
import { VideoUploadPanel } from "./VideoUploadPanel";

export function Dashboard() {
  const { connected, alerts } = useAlertSocket(8);

  return (
    <div className="dashboard-grid">
      <CaptureController />
      <VideoUploadPanel />
      <EventHistory />
      <AlertFeed connected={connected} alerts={alerts} />
    </div>
  );
}
