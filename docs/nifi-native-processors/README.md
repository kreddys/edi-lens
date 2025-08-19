# NiFi Native Python Processors Enhancement

This directory contains the design documentation for migrating EDI processing services from backend API calls to native NiFi Python processors.

## Project Objective

Transform the current architecture where NiFi workflows invoke backend REST APIs for EDI processing into a self-contained system where EDI services run natively within NiFi using Python processors.

## Documentation Structure

1. **[01-overview-and-architecture.md](./01-overview-and-architecture.md)** - High-level architecture overview and design principles
2. **[02-processor-specifications.md](./02-processor-specifications.md)** - Detailed specifications for each Python processor
3. **[03-migration-strategy.md](./03-migration-strategy.md)** - Incremental migration approach and phases
4. **[04-testing-strategy.md](./04-testing-strategy.md)** - Comprehensive testing plan for each phase
5. **[05-implementation-roadmap.md](./05-implementation-roadmap.md)** - Timeline and deliverables

## Key Benefits

- **Performance**: Eliminate HTTP overhead between NiFi and backend
- **Reliability**: Remove network dependencies for core EDI processing
- **Scalability**: Leverage native NiFi clustering and distribution
- **Maintainability**: Centralize EDI logic in reusable processors
- **Flexibility**: Enable custom workflow compositions

## Current Status

📋 **Planning Phase** - Design documentation in progress

## Quick Navigation

- [Architecture Overview](./01-overview-and-architecture.md)
- [Implementation Plan](./05-implementation-roadmap.md)
- [Testing Strategy](./04-testing-strategy.md)