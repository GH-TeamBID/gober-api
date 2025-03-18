# Implementation plan

## Phase 2: Frontend Development - Done

*This project is primarily a RESTful API backend; however, a minimal frontend component for accessing API documentation can be provided.*

1.  Confirm that FastAPI's automatic OpenAPI/Swagger docs (available at `/docs` and `/redoc`) meet the frontend requirements. **Reference: Requirements & Preferences: Documentation** - Done
    - Verified that FastAPI's automatic OpenAPI/Swagger docs are accessible at `/docs` and `/redoc`.
    
2.  (Optional) Create a simple landing page if desired. Create a file `/app/static/index.html` that includes links to the Swagger UI. **Reference: Frontend Components** - Done
    - Created a static directory and added a simple landing page with links to Swagger UI and ReDoc.
    - Updated main.py to serve static files and redirect the root to the landing page.
    
3.  **Validation**: Run the API with `uvicorn app.main:app --reload` and verify the Swagger UI is accessible at `http://localhost:8000/docs`. - Done
    - Verified that the Swagger UI is accessible at `http://localhost:8000/docs`.
    - Verified that the landing page is accessible at `http://localhost:8000/`.

## Phase 3: Backend Development

1.  In `/app/core/config.py`, build a centralized configuration module to manage environment variables (e.g., database URIs, JWT secret keys). **Reference: Project Structure: core/config.py** - Done
    - Enhanced the existing configuration module to include settings for Neptune, MeiliSearch, logging, and AI services.
    - Added environment variable mappings for all configuration settings.

2.  In `/app/core/database.py`, implement the database connection handlers for Azure SQL Database and Amazon Neptune. **Reference: Tech Stack: Databases** - Done
    - Enhanced the existing database connection module to include handlers for Amazon Neptune and MeiliSearch.
    - Added proper error handling and logging for database connections.

3.  In `/app/core/init_db.py`, write a script to initialize database schemas. **Reference: Project Structure: core/init_db.py** - Done
    - Enhanced the existing initialization script to include Neptune and MeiliSearch initialization.
    - Added proper error handling and logging for database initialization.
    - Created an `init_all()` function to initialize all database components.

4.  In `/app/main.py`, initialize the FastAPI app instance and include middleware for logging and error handling. **Reference: Core Features: Performance & Security** - Done
    - Added middleware for request logging with timing information.
    - Added global exception handlers for validation errors and unexpected errors.
    - Added a health check endpoint for monitoring.

5.  In `/app/modules/auth`, create a file (e.g., `routes.py`) that defines endpoints:

    *   `POST /api/auth/signup`
    *   `POST /api/auth/login`
    *   `POST /api/auth/logout`
    *   `PUT /api/auth/password` Use JWT for authentication and bcrypt for password hashing. **Reference: Core Features: User Management and Authentication** - Done
    - Enhanced the existing auth routes to include endpoints for signup, login, logout, and password update.
    - Implemented JWT authentication and bcrypt password hashing.
    - Added a `/me` endpoint to retrieve the current user's information.

6.  In `/app/modules/auth`, create a `schemas.py` to define Pydantic models for user registration and login. **Reference: Requirements & Preferences: Consistency** - Done
    - Enhanced the existing schemas to include models for user creation, response, login, and password update.
    - Added validation rules for fields like username, password, and email.

7.  In `/app/modules/auth`, create a `services.py` file to handle business logic for authentication (e.g., token generation, password encryption). **Reference: Requirements & Preferences: Modularity** - Done
    - Enhanced the existing services to include functions for user creation, authentication, and password management.
    - Implemented JWT token generation and validation.
    - Added a dependency for retrieving the current authenticated user.

8.  In `/app/modules/tenders`, create a file (e.g., `routes.py`) that defines endpoints:

    *   `GET /api/tenders` (with filtering, sorting, and pagination)
    *   `GET /api/tenders/{id}`
    *   `POST /api/tenders/{id}/save` (toggle save/unsave)
    *   `GET /api/tenders/saved`
    *   `PUT /api/tenders/{id}/ai-summary`
    *   `PUT /api/tenders/{id}/ai-document` **Reference: Core Features: Tender Management** - Done
    - Implemented all required tender endpoints with proper request validation and response models.
    - Configured tenders to be retrieved from the RDF graph in Amazon Neptune.
    - Implemented the save/unsave functionality using a ClientTender relationship table in SQL.
    - Implemented the saved tenders endpoint to first get IDs from SQL and then fetch details from Neptune.
    - Added an endpoint for updating AI-generated summaries stored in the SummaryTender table.
    - Added an endpoint for retrieving tender types.

9.  In `/app/modules/tenders`, create a `schemas.py` to define Pydantic models for tender details and AI content updates. **Reference: Requirements & Preferences: Consistency** - Done
    - Created Pydantic models for tender responses and filtering.
    - Added models for AI content updates and tender type responses.
    - Implemented validation rules for tender fields.

10. In `/app/modules/search`, create endpoints in a new module (e.g., a file `routes.py` in `/app/modules/search`) for:

    *   `GET/PUT /api/search-criteria`
    *   `GET /api/tender-types` **Reference: Core Features: Search Criteria Management**

11. In `/app/modules/ai_tools`, implement integration logic to handle asynchronous tasks that interact with the internal Gemini API. Use FastAPI's BackgroundTasks to manage long-running operations. **Reference: Core Features: Asynchronous Processes & LLM Interaction Details**

12. Configure global exception handlers and logging using FastAPI middleware. **Reference: Requirements & Preferences: Logging/Monitoring/Error Reporting**

13. Write unit and integration tests for each module. Create tests in a directory `/tests/` corresponding to each module (e.g., `/tests/test_auth.py`). **Reference: Requirements & Preferences: Performance**

14. **Validation**: Run the application and execute test endpoints using `curl` or API testing tools to verify all endpoints return the expected status codes and JSON structures.

## Phase 4: Integration

1.  Integrate JWT authentication middleware into the FastAPI app to secure protected routes. **Reference: Core Features: User Management and Authentication**
2.  Integrate the database connection logic from `/app/core/database.py` into each module requiring data persistence. **Reference: Tech Stack: Databases**
3.  Integrate the asynchronous tasks from the AI tools module into tender update endpoints ensuring non-blocking operations. **Reference: Core Features: Asynchronous Processes**
4.  Integrate MeiliSearch Cloud as the search engine; configure a client in the configuration module and use it within the search criteria endpoints. **Reference: Tech Stack: Search Engine**
5.  Merge API routes from different modules in `/app/main.py` using FastAPI's router inclusion mechanism. **Reference: Requirements & Preferences: Modularity**
6.  **Validation**: Run end-to-end API calls using Postman or curl to ensure that integrated functionality (authentication, tender management, search criteria, and async tasks) works as expected.

## Phase 5: Deployment

1.  Create a `Dockerfile` in the project root to containerize the FastAPI application. Include instructions to copy the app directory and install dependencies. **Reference: Tech Stack: Containerization**
2.  Create a `docker-compose.yml` file that sets up containers for the FastAPI app, Azure SQL Database (simulate for development), and any required services like MeiliSearch if possible. **Reference: Tech Stack: Containerization**
3.  Write environment-specific configuration files (e.g., `.env.development`, `.env.staging`, `.env.production`) to store environment variables like database URIs and JWT secrets. **Reference: Requirements & Preferences: Environments**
4.  Set up an Azure DevOps pipeline configuration file (e.g., `azure-pipelines.yml`) to automate testing and building of the Docker image. **Reference: Tech Stack: CI/CD**
5.  Configure the pipeline to run unit tests and build a Docker image upon commit to the repository. **Reference: Requirements & Preferences: CI/CD**
6.  Set up deployment scripts in the pipeline to deploy the containerized API to your chosen cloud target (e.g., Azure Container Instances or Azure Kubernetes Service). **Reference: Tech Stack: Deployment**
7.  Include deployment configuration files (e.g., Kubernetes YAML definitions or Azure container configurations) in `/infra/` if applicable. **Reference: Requirements & Preferences: Deployment**
8.  Configure logging, monitoring, and error reporting in production using available cloud services. **Reference: Requirements & Preferences: Logging/Monitoring/Error Reporting**
9.  **Validation**: After deployment, perform end-to-end testing on the staging environment to ensure that all API endpoints are working as expected and that CI/CD pipeline triggers are successful.

## Final Checks and Documentation

1.  Verify that the automatic OpenAPI/Swagger documentation is accessible in all environments. **Reference: Requirements & Preferences: Documentation**
2.  Update README.md with detailed setup, development, and deployment instructions, including environment variable configurations. **Reference: Requirements & Preferences: Documentation**
3.  Review the implementation to ensure modularity and scalability; perform a code review using the provided AI tools (Claude 3.7 Sonnet, Deepseek R1, and Claude 3.5 Sonnet) if needed. **Reference: Core Features: Modularity & AI Tools**
4.  Document integration details and edge cases in the project wiki or documentation files. **Reference: Requirements & Preferences: Documentation**
5.  **Validation**: Run final integration tests using tools such as Postman and automated scripts to simulate concurrent API requests, ensuring rate limiting/caching strategies work as expected.

This concludes the step-by-step implementation plan for the Gober API based on the provided project requirements. Each step is designed to ensure clear separation of responsibilities, proper integration of components, and reliable deployment following the outlined tech stack and best practices.
