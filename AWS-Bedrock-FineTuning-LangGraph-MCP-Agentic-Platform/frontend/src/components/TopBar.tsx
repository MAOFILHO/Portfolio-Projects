import { ContosoLogo } from "./ContosoLogo";

interface TopBarProps {
  username: string;
  onSignOut: () => void;
}

export function TopBar({ username, onSignOut }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar-brand">
        <ContosoLogo />
        <span>Contoso</span>
      </div>
      <div className="top-bar-session">
        <span>Signed in as {username}</span>
        <a onClick={onSignOut}>Sign out</a>
      </div>
    </header>
  );
}
