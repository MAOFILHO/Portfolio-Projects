The auth-service repo has an open change request titled "Add rate limiting
to login endpoint". Confirm its current status, then consult the runbook
titled "Responding to a login brute-force spike" for guidance before
deploying auth-service.

Create a staging deploy for the auth-service repo, then mark that deploy
succeeded once it completes.
