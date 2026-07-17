"""Static content for the Learn page, extracted once from the three provided
study guides (Microservices Article.pdf, Senior Python Engineer's Guide to
Microservices Migration.pdf, Modernizing Architectures — Strangler Fig
Pattern.pdf). Not fetched at runtime — this is the source of truth."""

LEARN_CONTENT = {
    "advantages": [
        {
            "title": "Independent scaling",
            "body": "Each service is deployed separately and scales horizontally based on its own "
                     "load profile — e.g. checkout or catalog under heavy traffic — without scaling "
                     "the whole system and wasting resources on idle components.",
        },
        {
            "title": "Faster, safer change cycles",
            "body": "Teams deploy changes to one service without redeploying the entire system, "
                     "reducing blast radius and supporting real CI/CD.",
        },
        {
            "title": "Technology and data autonomy",
            "body": "Different services can use different languages, frameworks, and databases "
                     "optimized for their workload (Polyglot Persistence).",
        },
        {
            "title": "Organizational alignment (Conway's Law)",
            "body": "Software architecture tends to mirror the communication structure of the "
                     "organization that built it. Small, autonomous 'Two-Pizza Teams' can own a "
                     "service end-to-end — from creation to maintenance.",
        },
        {
            "title": "Resilience and fault isolation",
            "body": "Failures are often localized to a single service; with retries, timeouts, and "
                     "circuit breakers, the system degrades gracefully instead of going down entirely.",
        },
    ],
    "strangler_fig_steps": [
        "Domain Assessment and Slicing — identify coherent business domains using Domain-Driven Design.",
        "Introduction of the Proxy Layer — place an API Gateway/BFF in front of the monolith; 100% of traffic still goes to it.",
        "Service Extraction — clone a high-value, well-isolated capability into a new independently deployable service.",
        "Anti-Corruption Layer (ACL) — an adapter that lets the remaining monolith (or sibling services) call the new service without leaking legacy assumptions.",
        "Traffic Redirection — update the proxy to route specific paths to the new microservice.",
        "Data Synchronization and Ownership — move relevant data to a service-specific store; use a synchronizing agent if the legacy database still needs it.",
        "Decommissioning — repeat extraction until the monolith is a skeleton, then retire it.",
    ],
    "anti_patterns": {
        "technical": [
            {"name": "Shared Persistence", "why": "Multiple services reading/writing the same schema couples them at the data layer and removes team independence."},
            {"name": "Megaservice", "why": "A service that absorbs too many responsibilities becomes a 'mini-monolith'."},
            {"name": "Cyclic Dependency", "why": "A → B → C → A call chains make services impossible to deploy or test in isolation."},
            {"name": "Hardcoded Endpoints", "why": "Hardcoding IPs/ports instead of service discovery breaks the moment topology changes."},
            {"name": "Inappropriate Service Intimacy", "why": "Reaching into another service's private data instead of using its public API."},
            {"name": "Shared Libraries for business logic", "why": "Forces synchronized deployments across services that should be independent."},
        ],
        "organizational": [
            {"name": "Microservices as the Goal", "why": "Adopting the architecture for its own sake, not for a concrete scale/velocity need."},
            {"name": "Legacy Organization", "why": "Rigid, siloed Dev/Ops teams and manual release schedules negate most microservices benefits."},
            {"name": "Magic Pixie Dust", "why": "The belief that the architecture alone fixes organizational problems."},
        ],
    },
    "glossary": {
        "Anti-Corruption Layer (ACL)": "A facade/adapter that translates calls between a legacy system and a new microservice during migration.",
        "Bounded Context": "A DDD pattern defining the boundary within which a specific domain model applies.",
        "Circuit Breaker": "Returns an immediate failure for an operation likely to fail, preventing cascading resource exhaustion.",
        "Distributed Monolith": "Multiple services so tightly coupled they must be deployed/scaled together — the failure mode this migration avoids.",
        "Polyglot Persistence": "Using different database technologies per service, matched to its needs.",
        "Two-Pizza Team": "An autonomous team small enough to be fed by two pizzas, owning a service end-to-end.",
        "Wrong Cuts": "Splitting services along technical layers (presentation vs. data) instead of business capabilities.",
        "Synchronizing Agent": "A tactical bridge keeping a new microservice's data consistent with the legacy database during migration.",
    },
    "faq": [
        {
            "q": "Why not just rewrite the whole thing (\"Big Bang\")?",
            "a": "A rewrite delivers no value until the very end and risks losing lost/rediscovered requirements. The Strangler Fig pattern delivers value incrementally and lets the business pause without losing all progress.",
        },
        {
            "q": "Do we need Kubernetes to do microservices?",
            "a": "No — microservices are an architectural style; containers/Kubernetes are a common but not required packaging mechanism. This project itself proves it: it runs as plain Python processes locally and as Azure Container Apps in the cloud.",
        },
        {
            "q": "When is a monolith the better choice?",
            "a": "When simplicity is the priority, domain boundaries aren't well understood yet (avoiding 'Wrong Cuts'), or the application is small enough that distributed-systems overhead outweighs the benefit.",
        },
    ],
}
