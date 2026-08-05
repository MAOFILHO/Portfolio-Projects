import { Outlet } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { Sidebar } from "./Sidebar";

export function AppShell() {
  return (
    <div className="app-shell">
      <Navbar />
      <div className="app-body">
        <Sidebar />
        <main className="dashboard">
          <Outlet />
        </main>
      </div>
      <footer className="footer">
        Contoso &middot; Bombay Surface Temperature Forecasting &middot; ARIMA + SARIMAX + LSTM
        (TensorFlow &amp; PyTorch)
      </footer>
    </div>
  );
}
