-- /tickets namespace schema. Re-run to reset and reload: drops then recreates
-- everything, so this file is the one source of truth for both the seed
-- script (Ticket 02, item 3) and test setup.

DROP TABLE IF EXISTS review_comments;
DROP TABLE IF EXISTS change_requests;
DROP TABLE IF EXISTS deploys;
DROP TABLE IF EXISTS runbook_acknowledgements;
DROP TABLE IF EXISTS runbooks;
DROP TABLE IF EXISTS repos;
DROP TABLE IF EXISTS attachments;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'standard'
);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    assignee TEXT,
    customer_id INTEGER REFERENCES customers(id)
);

CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    body TEXT NOT NULL
);

CREATE TABLE attachments (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    filename TEXT NOT NULL
);

CREATE TABLE repos (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE change_requests (
    id SERIAL PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    title TEXT NOT NULL,
    diff TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE review_comments (
    id SERIAL PRIMARY KEY,
    change_request_id INTEGER NOT NULL REFERENCES change_requests(id),
    body TEXT NOT NULL
);

CREATE TABLE runbooks (
    id SERIAL PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    internal_notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE runbook_acknowledgements (
    id SERIAL PRIMARY KEY,
    runbook_id INTEGER NOT NULL REFERENCES runbooks(id),
    note TEXT NOT NULL
);

CREATE TABLE deploys (
    id SERIAL PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    environment TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
