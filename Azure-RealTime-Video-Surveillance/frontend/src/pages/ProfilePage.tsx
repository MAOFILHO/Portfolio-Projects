import type { ClientPrincipal } from "../hooks/useAuth";

interface ProfilePageProps {
  user: ClientPrincipal | null;
}

export function ProfilePage({ user }: ProfilePageProps) {
  return (
    <div className="panel">
      <h3>Profile</h3>
      {user ? (
        <dl className="profile-fields">
          <dt>Name</dt>
          <dd>{user.userDetails}</dd>
          <dt>Identity provider</dt>
          <dd>{user.identityProvider}</dd>
          <dt>User ID</dt>
          <dd>{user.userId}</dd>
          <dt>Roles</dt>
          <dd>{user.userRoles.join(", ")}</dd>
        </dl>
      ) : (
        <p className="empty-state">Not signed in.</p>
      )}
      <a className="button-link" href="/.auth/logout?post_logout_redirect_uri=/">
        Sign out
      </a>
    </div>
  );
}
