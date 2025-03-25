# Project Requirements Document (PRD) for Gober API

## 1. Project Overview

Gober API is designed as a robust and scalable backend RESTful API built using FastAPI. The core of this project is to manage users, bids (tenders), and custom search criteria while orchestrating long-running asynchronous tasks such as generating summaries and documents using AI. The API acts as the backbone for diverse client types—from administrators and account managers to operational teams and AI specialists—ensuring secure, high-performance endpoints that centralize business logic and maintain data integrity.

The API is being built to centralize the complex operations across the application by handling user authentication, tender management (including filtering, sorting, and detailed data retrieval), and AI-driven processes in a modular and maintainable way. Key objectives include delivering secure endpoints with robust logging and error reporting, ensuring the asynchronous tasks do not degrade performance, and enabling smooth integration with containers and CI/CD pipelines through platforms such as Azure DevOps and Docker.

## 2. In-Scope vs. Out-of-Scope

**In-Scope:**

*   Development of a RESTful API using FastAPI.
*   Endpoints for user registration, login, logout, and account management, featuring JWT-based authentication and password encryption.
*   Tender management endpoints that offer listing, filtering, sorting, pagination, detailed view, and save/unsave functionality.
*   Endpoints for managing and updating user-specific search criteria, including retrieval of tender types.
*   Implementation of asynchronous processes to handle long-running tasks (e.g., interactions with Gemini-based LLM processes for generating summaries and documents).
*   Robust logging, monitoring, and error reporting integrated into every endpoint.
*   Modular project structure with dedicated directories for authentication, clients, tenders, and AI tools.
*   Support for multiple deployment environments (development, staging, production) with CI/CD pipelines (Azure DevOps) and containerization (Docker).

**Out-of-Scope:**

*   Granular or additional user roles and permissions beyond basic demo-level functionality.
*   Defined performance benchmarks and load testing parameters (since this is currently at demo phase).
*   Advanced caching strategies and rate limiting mechanisms beyond simple initial implementations.
*   Full-scale production-level deployments or integrations until the demo phase is successfully validated.

## 3. User Flow

When a new user accesses the web application, their journey begins with account creation and authentication. The user fills out registration details which are handled by the /api/auth/signup endpoint. Once the registration is complete, the user logs in via the /api/auth/login endpoint, receiving a JWT token that will be used for all subsequent secure interactions. Upon logging in, the application directs them to a dashboard, where session management endpoints are available (like logout and password updates) to securely manage their account.

After authentication, the user proceeds to the tender management section where they can browse available tenders. They can filter, sort, and paginate through tenders using the dedicated endpoint. When a specific tender is selected, detailed information is displayed, and the user can opt to save or unsave the tender based on their preference. Further, users can customize their search criteria through endpoints designed for updating or retrieving saved filters. In the background, when requested, asynchronous operations are triggered to generate AI-driven summaries and documents through multiple calls to an internal API that interfaces with the Gemini LLM, ensuring the system remains responsive and informative.

## 4. Core Features (Bullet Points)

*   **User Management and Authentication**

    *   Endpoints for user signup (/api/auth/signup), login (/api/auth/login), logout (/api/auth/logout), and password updates (/api/auth/password).
    *   JWT-based authentication to secure endpoints and protect sensitive data.
    *   Administrative functionalities such as listing all users (/api/users) and removing users (/api/users/:id).

*   **Tender Management**

    *   Endpoints to retrieve a list of tenders with filtering, sorting, and pagination (/api/tenders).
    *   Endpoint to get detailed tender information (/api/tenders/:id).
    *   Functionality to save/unsave tenders (/api/tenders/:id/save) and retrieve saved tenders (/api/tenders/saved).
    *   Endpoints to update AI-generated tender summaries (/api/tenders/:id/ai-summary) and documents (/api/tenders/:id/ai-document).

*   **Search Criteria Management**

    *   Retrieve and update user-specific saved search criteria (/api/search-criteria).
    *   Retrieve a list of available tender types (/api/tender-types) for enhanced filtering options.

*   **Asynchronous Operations**

    *   Handling long-running tasks through asynchronous endpoints to generate summaries and documents via repeated calls to an internal API using Gemini LLM.
    *   Ensuring that these asynchronous tasks do not block or degrade the responsiveness of the user interface.

*   **Logging, Monitoring, and Error Reporting**

    *   Integrated robust logging and monitoring mechanisms for every significant operation.
    *   Detailed error reporting to ensure issues can be quickly identified and resolved.

*   **Modular Architecture**

    *   Organized directory structure separating core configuration, authentication, client management, tender handling, and AI tools.
    *   Centralized management for configurations and database connections.

## 5. Tech Stack & Tools

*   **Frontend/Consumers:**

    *   The API is designed to be consumed by a web application (frontend details not covered in this PRD).

*   **Backend:**

    *   Programming Language & Framework: Python with FastAPI.
    *   Databases: Azure SQL Database for relational data and Amazon Neptune for graph-based data.
    *   Search Engine: MeiliSearch Cloud.
    *   Asynchronous Task Handling: FastAPI’s asynchronous capabilities for background tasks.

*   **AI Integrations:**

    *   LLM: Gemini for AI-driven summarizations and document generation.

*   **Tooling & Environment:**

    *   Containerization: Docker.
    *   Continuous Integration/Delivery: Azure DevOps.
    *   IDEs and Code Assist Tools: Cursor for enhanced coding capabilities.
    *   Additional AI-Powered Design/Code Assistance: Tools such as Claude 3.7 Sonnet, Deepseek R1, and Claude 3.5 Sonnet for code insight and completion.
    *   Automated Documentation: Swagger/OpenAPI (auto-generated by FastAPI).

## 6. Non-Functional Requirements

*   **Performance:**

    *   The API should provide high performance even when performing resource-intensive asynchronous tasks.
    *   Although specific benchmarks are not set for the demo phase, initial deployments are expected to maintain responsiveness during long-running tasks.

*   **Security:**

    *   Use secure JWT-based authentication and password encryption.
    *   Adhere to industry-standard security practices in terms of data handling and endpoint protection.
    *   Ensure robust role management for demo purposes (basic admin and user functionalities).

*   **Compliance & Usability:**

    *   Automatic documentation generation via Swagger/OpenAPI for ease of integration and user understanding.
    *   Clear error codes and descriptive messages must be included to aid in debugging and user feedback.

*   **Monitoring & Logging:**

    *   Implement a robust logging system to capture detailed request/response cycles.
    *   Incorporate error reporting and performance monitoring to quickly identify and troubleshoot issues.

## 7. Constraints & Assumptions

*   **Constraints:**

    *   The project is currently at a demo phase, so granular role-based permissions beyond basic functionalities are not implemented.
    *   Specific performance benchmarks (like maximum concurrent users) are not established yet.
    *   The asynchronous tasks rely on multiple calls to an internal API for processing with Gemini, which may add complexity.

*   **Assumptions:**

    *   The API will be deployed in distinct environments (development, staging, production) using containerization and CI/CD pipelines.
    *   The services (databases, search engine, etc.) are assumed to be available and properly configured as per requirements.
    *   Basic caching and rate limiting strategies will be implemented during the demo phase but might need adjustment for full-scale production.
    *   The use of industry-standard best practices will ensure that even with demo-level performance, the API remains secure and maintainable.

## 8. Known Issues & Potential Pitfalls

*   **Technical Hurdles:**

    *   Handling asynchronous tasks, particularly those involving multiple interactions with the internal API for Gemini LLM, may lead to increased complexity. Mitigation: Use robust async frameworks and careful error handling with retries as needed.
    *   Integration of logging, monitoring, and error reporting requires careful design to avoid performance overhead. Mitigation: Use optimized logging libraries and ensure non-blocking I/O operations.
    *   Setting up multiple environments (development, staging, production) might introduce configuration inconsistencies. Mitigation: Maintain strict environment parity policies and centralized configuration management.

*   **Potential Pitfalls:**

    *   The demo phase might not fully replicate production load, leading to unforeseen performance issues when scaling. Mitigation: Plan for load testing and deploy simple caching and rate limiting strategies early.
    *   Security risks around JWT management and password encryption must be vigilantly monitored. Mitigation: Regular security audits and adherence to best practices.
    *   Dependency on external services like Gemini and internal APIs for AI tasks may impact task reliability. Mitigation: Implement robust error handling, logging, and fallback mechanisms to ensure system resilience.

This document serves as the main reference for all future technical documentation regarding the Gober API project. It aims to leave no room for ambiguity by clearly outlining the project's objectives, scope, user experience, core features, technology stack, and essential non-functional requirements, along with the constraints and potential technical pitfalls.
