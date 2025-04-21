# Python API

See also: [Web API Docs](/docs/api)

## [`config`](./config.md)

Sitewide and per-service configuration.

## Models

### [`models`](models/)

Primary data and database models used within sciop.

### [`mixins`](./mixins.md)

Mixin models that behave as "traits" for models,
enabling shared behavior for search, e.g. editing, permissions, etc.

### [`types`](./types.md)

Field- and item-level types, enums.

## Server

### [`deps`](./deps.md)

Per-endpoint dependencies for handling auth, model loading.

### [`middleware`](./middleware.md)

Middleware that handles HTTP and API responses, e.g. logging, rate limiting.

### [`services`](./services.md)

Scheduled background services

## Database

### [`db`](./db.md)

Main db interaction methods

### [`crud`](./crud.md)

Frequently reused db operations

## Plumbing

### [`logging`](./logging.md)

Logging initialization and configuration

### [`scheduler`](./scheduler.md) 

Scheduled task runner and decorators

### [`exceptions`](./exceptions.md)

Sciop-specific exceptions