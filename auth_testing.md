Auth-Gated App Testing Playbook (copy of the integration expert instructions)
See /app/memory/test_credentials.md for a working mongosh snippet to seed a test user/session.

1. Seed user + session in MongoDB (collection: users, user_sessions)
2. Set cookie session_token on the app domain OR pass Authorization: Bearer <token>
3. Verify /api/auth/me returns user data
4. Exercise protected endpoints
