# Tradefly - LLM Rebuild Blueprint

This document serves as a comprehensive technical blueprint for an LLM to rebuild the Tradefly application from scratch. It details the existing core functionality to be retained, deprecated code to exclude, and new required features to be implemented during the rebuild.

## 1. Project Overview & Architecture
**Tradefly** is an automated crypto trading signal processor. It ingests trading signals from multiple sources (TradingView webhooks, Discord messages from the "Bandit" bot), parses them (using Google's Gemini API for NLP), matches them to user subscriptions, and dispatches trade execution orders to exchange-specific queues (e.g., Bitunix).

### Tech Stack for Rebuild:
*   **Backend:** Django, Django REST Framework (DRF)
*   **API Architecture (Mobile-Ready):** The backend *must* be built as a strict, headless JSON API (API-First Design). Avoid tightly coupling business logic into Django HTML templates, ensuring that a future dedicated iOS/Android app can consume the exact same endpoints as the web dashboard.
*   **API Documentation:** Auto-generated OpenAPI/Swagger spec via `drf-spectacular` for future expandability and native app integration.
*   **Database:** PostgreSQL (via `psycopg2`)
*   **LLM Parsing:** Google Generative AI (`google-generativeai`)
*   **Background Tasks & Queues:** Abstracted Queue Interface supporting AWS SQS (existing), Redis/Celery (new), and Database Queues (new).
*   **Frontend GUI (New):** A modern JS framework like React/Next.js (Highly Recommended) or Vue/Nuxt.js, communicating with the Django backend via REST API. 
    *   *Mobile App Pathway:* By utilizing React for the web frontend, developers can reuse significant portions of UI logic, state management, and API client code if/when a dedicated mobile app is built using React Native.
    *   *Progressive Web App (PWA):* The web application must be configured as a PWA (including `manifest.json` and basic service workers) so users can immediately "Install to Home Screen" on iOS/Android for an app-like experience before native apps are even launched.
    *   *Templating Architecture:* The frontend system must be structured to support injecting multiple pre-built, stylized UI templates simultaneously.
    *   *Theme Universality:* UI design/CSS implementations selected for the external-facing pages must gracefully follow through to the authenticated application views to maintain a cohesive brand.

---

## 2. Core Features & Modularity

### A. Signal Ingestion
1.  **Webhooks (TradingView / Others):** Endpoints receiving formatted JSON signals. Must include IP allowlisting AND require a cryptographic secret token in the URL or payload to guarantee authenticity. The application must support multiple distinct webhook endpoints, managed via the Admin Dashboard.
2.  **Discord Bot (Bandit) Integration:** An API endpoint (`/api/bandit/`) receiving raw text messages from Discord channels. 
    *   **New Requirement:** This endpoint *must* be secured with API Key authentication. There may be multiple distinct bot clients relying on this endpoint. The endpoint logic must isolate incoming signals based on the authorized client credential. The blueprint expects the LLM to design the authentication scheme (e.g., token-based) and provide clear documentation on how the external client applications must be configured to pass this token in their headers.

### B. Signal Parsing (Gemini Integration)
*   Discord messages are routed based on channel name.
*   The raw text is sent to the Gemini API (`gemini-2.5-flash`) using highly structured prompts (Few-Shot Prompting).
*   Gemini returns a strict JSON schema representing the trade (Asset, Side, Entry, Take Profits, Stop Loss).

### C. Trade Dispatch & Queueing (SQS to Lambda)
*   Once a signal is validated and saved, the system finds all active `StrategySubscription`s for that signal's strategy.
*   Exchange-specific formatting (e.g., Bitunix batch order payload) is generated.
*   Orders are pushed to an Amazon SQS queue.
*   **Lambda Execution:** An AWS Lambda function consumes messages from the SQS queue, authenticates with the user's exchange API keys (decrypted securely), and executes the trade. *Crucial:* The Lambda function must implement robust exponential backoff and retry logic to gracefully handle `429 Too Many Requests` or temporary `50X` errors from the exchange APIs.
*   **Django Callback:** The Lambda function must report the execution results (success, failure, order IDs, executed prices) back to a secure Django webhook (`/api/trade-callback/`). Django then updates the `UserTrade` record in the database.
*   *Note:* The Python code for this Lambda function must be developed and maintained within this Django project's repository (e.g., in a `lambda/` directory) to ensure compatibility. It will be manually deployed by the admin. Comprehensive documentation on setting up the SQS trigger, IAM roles, and Lambda environment variables must be included.

### D. Exchange Integrations Architecture (Futures & Margin)
*   **Futures/Margin Focus:** The application exclusively targets futures and margin trading features, NOT spot trading. All payload formatting and exchange interactions must account for leverage, margin types, and futures-specific parameters.
*   **Integration Flexibility:** The core routing logic must be sufficiently abstracted to allow integrating exchanges via generalized libraries (e.g., `ccxt`) AND via fully bespoke API clients crafted directly from an exchange's raw documentation when a generic wrapper is insufficient or buggy.
*   **Admin Controls:** Administrators must have a dedicated UI to globally enable or disable specific exchanges. This toggle triggers the waterfall deactivation mentioned in Section 7, freezing associated executing strategies.

---

## 3. Excluded / Deprecated Code (Sunset)
During the rebuild, ignore or remove the following dead code from the original source:
*   `BlogPost` model, views (`BlogPostListCreate`, `BlogPostRetrieveUpdateDestroy`, `BlogPostList`), and serializers.
*   `DoSomethingView` API endpoint.
*   Legacy Gemini testing endpoints (`callGeminiApi` view).
*   Hardcoded test/debugging scripts in API views.

---

## 4. Database Schema (Existing & to be Rebuilt)

*Critical Instruction for LLM:* The LLM is encouraged to design the most effective, efficient, and normalized database schema to support these features. It **DOES NOT** need to maintain strict parity with the legacy table structures, especially considering the shift to unified dynamic models (e.g., dropping hardcoded `HRJDiscordSignal` in favor of a unified `ParsedSignal` using `JSONField`).

### User & Authentication
*   **Extended UserProfile:** Linked to Django `User`. Contains personal info (address, phone).
*   **UserApi:** Encrypted storage for API keys (e.g., Bitunix, Binance). *Must implement proper field-level encryption (e.g., `fernet_fields`).*
*   **SupportedExchange:** Table of allowed exchanges (e.g., "Bitunix").

### Strategies & Triggers
*   **SignalTrigger:** Source of the signal (e.g., 'tradingview', 'discord_hrj').
*   **Strategy:** The actual trading strategy users subscribe to. Has a name, description, and auth password.
*   **StrategySubscription:** Maps a User to a Strategy and a `UserApi`. Stores leverage amount, portfolio percentage (0-100), max TP trades, and trailing SL preferences.

### Trades & Execution
*   **UserTrade:** Records actual executed trades, position IDs, and quantities linked back to the user and the original signal.
*   *Financial Data Integrity (Soft Deletes):* The LLM must implement "Soft Deletes" (e.g., `is_active=False`, `deleted_at` timestamp) for all financial and subscription models. `UserTrade`, `StrategySubscription`, and `UserApi` records should *never* be hard-deleted from the database to maintain absolute historical integrity.

---

## 5. NEW FEATURE: Dynamic Channel & Prompt Template Management
*Current flaw: Discord channel names, signal models (HRJ, FJ, SIGSCAN), and their Gemini prompts are hardcoded.*

**Rebuild Requirement:**
Admins must have maximum flexibility to add new signal channels on the fly via an intuitive UI.
1.  **Dynamic Prompt Model:** Create a `PromptTemplate` model storing the exact instructions, schema requirements, and few-shot examples for Gemini.
2.  **Dynamic Channel Routing:** A `DiscordChannel` model linking a specific Discord Channel ID/Name to a `PromptTemplate` and `Strategy`.
3.  **Unified Signal Storage:** Instead of hardcoded models (`HRJDiscordSignal`, `FJDiscordSignal`), use a unified `ParsedSignal` and `TakeProfitTarget` model, utilizing PostgreSQL `JSONField` for exchange-specific or signal-specific custom data to avoid schema migrations for every new channel.
4.  **Admin UI:** A user-friendly dashboard for Admins to view all channels, add a new one, type the LLM prompt in a large text area, and activate it instantly without deploying code.

---

## 6. NEW FEATURE: Advanced Trade Queue Redundancy & Routing
*Current flaw: Tightly coupled to Amazon SQS. If SQS fails, trades halt.*

**Rebuild Requirement:**
Create an agnostic queue dispatcher interface that supports primary and fallback routing for unparalleled application redundancy.
1.  **QueueProvider Model:** Admin toggles for queue backends. Must support multiple AWS SQS queues, Database Queues, Redis, and optionally allow the LLM to recommend/implement other 3rd party robust queueing systems (e.g., RabbitMQ, Google Cloud Tasks).
2.  **Routing & Priority Logic:** Admins must be able to configure queues with a strict priority order (e.g., Queue A is Primary, Queue B is Backup 1, Queue C is Backup 2). 
3.  **Failover Execution:** When `process_and_dispatch_signal()` runs, it attempts to dispatch to the highest priority active queue. If the primary queue is non-responsive or fails, it automatically routes the order to the next available backup in the priority sequence.
4.  *(Note for Worker side)*: The consumer workers must implement deduplication (e.g., checking if `Signal.id` + `User.id` trade was already executed via a Redis lock or Postgres unique constraint) to avoid duplicate buys.
5.  **Toggle Flexibility:** The entire redundancy failover feature can be completely disabled by the admin if they only wish to use a single queue.

---

## 7. NEW FEATURE: User Handling, GUI, and Analytics
*Current flaw: The project operates mostly as a headless API.*

**Rebuild Requirement:**
A complete, modern web-based dashboard for End-Users and Admins.
*   **Universal UI Requirements:** All data tables throughout the application (both User and Admin facing) *must* be fully sortable, searchable, and filterable. The UI must utilize intuitive "toast" notifications (e.g., success, error, warning popups) across all forms to immediately alert users/admins if something is incorrect, submitted successfully, or fails validation.

1.  **Lightweight CMS, Marketing Pages, and Dynamic Theming:**
    *   The application must include a light Content Management System (CMS) enabling the creation of external-facing marketing and landing pages that live outside the core authenticated application.
    *   *Template Switcher:* The system must allow Admins (or Designers) to drop in *multiple* pre-built CSS/UI templates and instantaneously switch the entire application's active visual theme via a dropdown in the Admin settings.
    *   *Marketplace Integration:* The application architecture must support (via API or direct package intake) pulling themes directly from popular template marketplaces so they can be applied dynamically without touching raw code.
    *   *Designer Access:* Establish a "UI Designer" role with minimal-access dashboard permissions. This allows a designer to log in and safely edit external-facing page content, apply templates, and tweak overarching CSS designs without gaining full application or database management privileges.
2.  **Authentication Flow:** Login, Registration, Password Reset, and **Two-Factor Authentication (2FA)** via Authenticator App (TOTP) to secure user funds/API keys.
    *   **OAuth / Social Login:** Implement one-click registration and login via external providers. At a minimum, include **Google** and **Apple** for mass-market ease. In the context of crypto/trading, also support **Discord** (which natively aligns with the Bandit bot architecture and could automatically link their Discord ID to their account for future feature expansion).
3.  **User Dashboard:**
    *   **Exchange Setup:** UI to add/verify (Bitunix) API keys.
    *   **Strategy Hub:** Browse available strategies, view historical performance, and subscribe.
    *   **Subscription Management:** Adjust portfolio percentage allocation, leverage slider, and risk limits per strategy. Users must have the ability to explicitly Subscribe, Unsubscribe, and temporarily Pause executions for any given strategy.
    *   **Support Ticketing System:** A dedicated UI section for logged-in users to submit, view, and reply to support/trouble tickets with administrators.
    *   **Trade History & Monitoring:** A robust UI table showing all triggered signals and resulting trades.
        *   *Real-time Updates:* Implement WebSockets (e.g., Django Channels) or Server-Sent Events (SSE) so that trade statuses update live on the user's screen without requiring page refreshes or heavy API polling.
        *   Clicking a specific trade expands to show real-time status queried directly from the exchange.
        *   Display the status of the initial entry order.
        *   Display the status of all associated Take Profit (TP) and Stop Loss (SL) orders.
        *   Calculate and display the current live Profit and Loss (PnL) for the open position based on the exchange's current mark price.
        *   **Data Export:** Provide an export button to download the current view of the table (filtered or unfiltered) as a CSV file for external analysis.
    *   **User Notifications Hub:** A dedicated section on the user profile where users can opt-in and manage email notifications for various application actions (e.g., trade executed, TP hit, API key expired).
3.  **Admin Dashboard (Custom or Extended Django Admin):**
    *   **UI/UX Architecture:** Prevent clutter. The LLM must design a manageable admin template that smartly utilizes tabs, accordions, and multiple distinct pages to organize the vast amount of controls, avoiding a single unwieldy "mega-page".
    *   **Dual Admin Roles (Plus Designer):** Implement distinct levels of administrator access assignable via a User Management page:
        *   *Super Admin (Full Access):* Can view all data and perform all C.R.U.D operations and settings modifications.
        *   *Observer Admin (Read-Only):* Can view all data, logs, and settings configurations, but is explicitly blocked from making any modifications.
        *   *UI Designer:* Can only access the CMS and templating sections to manage public pages and site-wide styling.
    *   **Strategy & Exchange Administration:** Admins must have full UI controls to create new strategies (that users can subsequently subscribe to) and to toggle the active status of any Strategy or supported Exchange (e.g., globally pausing Binance routing).
        *   **Waterfall Deactivation:** If an admin temporarily deactivates a Strategy or Exchange, the application must immediately cascade this state change down to the users. The relevant user `StrategySubscriptions` must be forcibly paused, and the application must dispatch proactive email notifications and UI alerts informing the users that the admin has disabled the feature, preventing them from re-enabling it until the admin reactivates the parent entity.
    *   **Webhook Manager:** A dedicated UI tool for administrators to manage ingest webhooks. Admins must be able to view, create, disable, and delete multiple webhook URLs for all signal methods. When a new webhook is generated by the Admin, the system must automatically include the necessary cryptographic tokens in the URL.
    *   **Bandit API Client Management:** A dedicated UI tool allowing the Admin to uniquely authorize, view, deactivate, and delete multiple distinct bot clients communicating with the `/api/bandit/` endpoint. Admins will generate the unique API tokens for the clients from this page.
    *   **Audit Logs:** Implement an administrative audit log tracking *who* did *what* and *when* (e.g., "Admin Kyle disabled the Binance exchange at 14:00").
    *   **User Impersonation:** A tool allowing Super Admins to temporarily log in as a specific user to troubleshoot dashboard issues without requiring the user's password.
    *   **Dynamic Channel Editor:** (As described in Section 5).
    *   **Integrated Ticketing Desk:** A master view for admins to read, assign, and respond to user trouble tickets. 
        *   **Email Integration:** The ticketing system must hook into the email notification system. When an admin replies to a ticket, the user gets an email. If the user or admin directly replies to that specific email thread from their mail client, the application must ingest that incoming email (e.g., via a unique reply-to address block or POP3 fetcher) and automatically append the response to the ticketing system in the web interface.
        *   **Documentation Requirement:** The LLM *must* create detailed, step-by-step documentation detailing exactly how the admin must configure the external Mail Server (SMTP/IMAP/POP3) and DNS records to fully support this automated email-to-ticket ingestion flow.
    *   **Advanced Analytics Rollup:** A high-level statistics view displaying:
        *   Total notional value of all trades executed system-wide.
        *   Count of all profitable vs. non-profitable trades.
        *   System-wide Net PnL (combining all user accounts).
    *   **Live Open Trades Monitor:** Stats and aggregate views highlighting all currently open positions held by users across the application.
    *   **Global Trade Ledger:** A master table allowing the admin to view, search, and filter every single trade executed by the application across all users.
        *   **Data Export:** Provide an export button to download the filtered or unfiltered trade data as a CSV file.
    *   **Global Mail Settings:** UI options to dynamically set email rate limiting (to avoid overburdening the SMTP server) or completely disable outbound mail.
    *   **Advanced Log Viewer:** A web interface allowing the Admin to view real-time system logs. Must display current log file sizes, and provide buttons to download and/or clear the log files to prevent server drive space exhaustion.

---

## 8. NEW FEATURE: Advanced Subscription & Tier Management
*Current flaw: No billing or access-tier system exists.*

**Rebuild Requirement:**
Implement a robust, modular subscription and tier system to monetize access to strategies.
1.  **Multiple Authorization Gateways:**
    *   The system must support integration with external payment processors (e.g., Polar.sh, LemonSqueezy, Stripe, PayPal, Cream).
    *   *Alternative Auth:* Support authorization where a user enters a User ID, and the application verifies their access via an external API or internal database check.
    *   *Toggle Flexibility:* Admins must be able to completely enable or disable individual subscription/payment modules from the dashboard.
2.  **Custom Subscription Tiers:**
    *   Admins must have a UI to create completely customizable tier levels (e.g., Free, Pro, Whale).
    *   For each tier, the Admin can define the **Cost Criteria** (dollar amount AND/OR an affiliate code requirement).
    *   For each tier, the Admin can restrict the **Maximum Number of Strategy Subscriptions** a user is allowed to hold simultaneously.
    *   For each tier, the Admin can whitelist exactly **Which Specific Strategies** the users in that tier are allowed to access.
3.  **Admin Overrides (Pro Access):**
    *   From the User Management dashboard, Admins must have the ability to explicitly grant individual users "Pro" or "Lifetime" access, completely bypassing the external subscription system and billing checks.

---

## 9. Infrastructure & Environment Setup
*Current flaw: Mixed environments and lack of automated deployment configurations.*

**Rebuild Requirement:**
The LLM must build the application with local development and production environments completely separated.
1.  **Django Settings Split:** Configure a `settings/` package containing `base.py`, `dev.py`, and `prod.py` to ensure local testing doesn't interfere with the server environment.
2.  **Environment Variables:** Create comprehensive `.env.example` and `.env.prod.example` files detailing all necessary keys (AWS, Gemini, Database, Mail Server SMTP credentials, Default Admin credentials, etc.) so the user can easily instantiate both environments.
3.  **Dokploy Integration:** The application will be deployed using Dokploy (a PaaS alternative). The LLM must reference general Dokploy deployment paradigms (e.g., creating a `dokploy.yml` or `docker-compose.yml` file, a production `Dockerfile`, and entrypoint scripts). 
4.  **Auto-Deployment Scripting:** Ensure the deployment configuration supports automatic rebuilds and container deployment when code is pushed to the target GitHub branch (e.g., configuring Dokploy webhooks or defining the correct build commands).
5.  **Automated Initialization:** The application's startup script (e.g., `entrypoint.sh`) must automatically check for and create an initial Django Superuser on the *first run* using credentials defined in the `.env` file.

---

## 10. Essential Security & System Health Requirements
*An automated financial application handling API keys and money requires strict security baselines.*

**Rebuild Requirement:**
1.  **Rate Limiting & Brute Force Protection:**
    *   Implement strict API rate limiting on the `/api/bandit/` endpoint and any authentication endpoints (Login/Password Reset) to prevent brute-force attacks.
    *   Administrators should be able to configure these rate limit thresholds from the Admin Dashboard.
2.  **IP Allowlisting UI:**
    *   The current IP allowlist for TradingView is hardcoded in the Python view. The LLM must move this to the database, giving Admins a UI to add, remove, and temporarily disable allowed IPs for webhooks.
3.  **Application Health Checks (Crucial for Dokploy):**
    *   Implement an unauthenticated `/healthz` endpoint that returns a `200 OK` JSON response.
    *   *Requirement:* This endpoint must internally verify that the PostgreSQL database is reachable and that the primary Queue (e.g., SQS) is accessible before returning 200. Dokploy and Docker will use this to know if the container is actually healthy and ready to route traffic, enabling zero-downtime deployments.
4.  **Database Backups:**
    *   The LLM must provide documentation or a cron-job script outlining how the PostgreSQL database should be automatically backed up (e.g., using Dokploy's built-in backup features or a custom `pg_dump` script to S3).
5.  **Concurrency & Race Conditions:**
    *   When the system updates `UserTrade` statuses, deducts portfolio balances, or handles webhook callbacks, the LLM must strictly use database row-level locking (e.g., Django's `select_for_update()`) to prevent race conditions when multiple concurrent signals or queue workers process simultaneously.

---

## 11. Advanced Logging Architecture
**Rebuild Requirement:**
A robust logging system is critical for a financial trading application. The LLM must implement a comprehensive, scalable logging framework.
1.  **Communication Logging:** All external API communications must be logged. This includes incoming requests from the Bandit API, outgoing requests/responses to the Gemini API, and all execution payloads/callbacks with User Exchanges and AWS SQS/Lambda.
2.  **Error & Debug Logging:** Detailed tracebacks for application errors and general debugging information. The LLM is empowered to add strategic log points wherever it deems useful.
3.  **File Management:** Logs must be written to rotating files. These files will be managed, downloaded, and cleared via the Admin Dashboard UI (as specified in Section 7).
4.  **Critical Failure Alerting:**
    *   If a catastrophic error occurs (e.g., an Exchange API is completely unreachable, the Lambda queue is dead-lettering, or the Gemini API quota is exhausted), the system must immediately dispatch an emergency alert to the Administrators (e.g., via Email or a dedicated Admin Discord Webhook).

---

## 12. Unit Testing Requirements
*Current flaw: Lack of automated tests makes refactoring dangerous.*

**Rebuild Requirement:**
The LLM must build the application using Test-Driven Development (TDD) principles. Comprehensive unit tests are completely mandatory to keep the codebase clean, robust, and free of regressions.
1.  **Test Framework:** Use Django's built-in `TestCase` and `pytest-django`.
2.  **Coverage Areas:**
    *   **Signal Parsing (Gemini):** Mock the Gemini API response to test that signals are correctly parsed into `ParsedSignal` and `TakeProfitTarget` objects, bypassing external network calls.
    *   **Queue Dispatching:** Mock `boto3` to ensure the correct payload formatting is sent to SQS based on different user configurations.
    *   **Dynamic Channels:** Test that an incoming Discord webhook routing matches the correct `PromptTemplate` and `Strategy` dynamically.
    *   **Lambda Callback endpoint:** Test that simulated success/failure callbacks from the Lambda correctly update the `UserTrade` status in the database.
    *   **Trade Monitoring UI:** Test that the views correctly aggregate and calculate PnL data based on mocked exchange API responses.
3.  **Execution Requirement:** The LLM must execute these tests iteratively as it writes the code, resolving any failures before moving to the next feature. Every feature merged must have accompanying passing tests.

---

## 13. Implementation Steps for LLM Rebuild
*Note: Unit testing is NOT a final step. TDD principles require that comprehensive unit tests must be written concurrently with every single numbered step below.*

When an LLM agent executes this rebuild, it should follow this sequence:
1.  **Initial Setup & Infrastructure:** Initialize Django, configure Postgres, setup OpenAPI/Swagger (`drf-spectacular`), split `dev.py`/`prod.py` settings, create `.env.example` files (with Mail & Superuser keys), and generate the Dokploy deployment and Auto-Superuser creation scripts.
2.  **Advanced Logging & Security Integration:** Implement the foundational file-based logging system for API communications and errors. Add rate limiting, DB/Queue Health Check endpoints, and the IP allowlisting database model.
3.  **Core Models & Subscriptions:** Build the Abstract User, UserProfile, Exchanges, UserApi, Strategy, Payment Gateways, Tier Levels, and Subscription models (incorporating the waterfall deactivation logic and custom tier rules).
4.  **Ticketing Models:** Build the models and email parsing mechanics for the integrated support desk.
5.  **Unified Signal & Prompt Models:** Build the dynamic `PromptTemplate`, `DiscordChannel`, and unified `ParsedSignal` architectures (replacing the hardcoded models).
6.  **Services Layer:** Implement `services.py` containing the logic for webhooks, duplicate checking, and Bitunix payload formatting.
7.  **Queue Layer:** Implement the abstract Queue Dispatcher with prioritized routing, failover logic, and primary/backup redundancy.
8.  **Gemini Client:** Rebuild `gemini.py` to dynamically fetch the prompt template from the database based on the incoming channel name.
9.  **Lambda Function Code:** Develop the standalone Python script for the AWS Lambda consumer, including the callback logic to Django. Write the AWS deployment documentation.
10. **Frontend GUI & Auth:** Scaffold the Django views/templates for API auth, 2FA, user onboarding, live trade monitoring (WebSockets/SSE), email notifications, and the Admin statistics ledger, including Mail Settings, Strategy Management, Webhook Management, API Client Management, Subscription Gateways, User Impersonation, Audit Logs, and the Log Viewer/Ticketing Desk.

---

## 14. Execution Strategy for the LLM
*To ensure a clean, efficient, and mistake-free build, the LLM and User must adhere to the following workflow:*

1.  **Iterative Step-by-Step Build:** Do NOT attempt to build the entire application in a single prompt. The User should instruct the LLM to complete exactly one numbered step from Section 13 at a time.
2.  **Test-Driven Execution:** For every step, the LLM must write the tests *first*, run them (expecting failures), write the implementation code, and then run the tests again until they pass. Do not move to the next feature until all tests for the current feature are green.
3.  **Context Injection:** When implementing specific third-party integrations (TradingView, Bitunix, Gemini), the User should provide snippet examples of actual JSON payloads or API responses to the LLM to eliminate guesswork.
4.  **Frequent Commits:** The LLM should encourage the User to commit to version control (Git) after every successful step to maintain a clean rollback point in case of AI hallucinations or errors.

---

## 15. Master System Prompt for Rebuild
*User: Copy and paste the prompt below into a fresh LLM conversation (with a clean workspace containing this blueprint) to kick off the project effectively.*

```text
You are an expert full-stack engineer, devops specialist, and solutions architect. Your task is to rebuild the 'Tradefly' application from scratch based on the attached `LLM_REBUILD_BLUEPRINT.md`.

Before writing any code, thoroughly read the blueprint to understand the dual-environment architecture, Dokploy deployment strategy, the new dynamic models, the failover queueing system, and the strict TDD (Test-Driven Development) requirements.

CRITICAL RULES FOR THIS ENGAGEMENT:
1. We will build this iteratively. DO NOT attempt to write the entire application at once.
2. We will follow Section 13 of the blueprint exactly, step-by-step.
3. For every feature, you must write comprehensive unit tests *first*, run them, implement the code, and run the tests again until they pass. Do not move on until coverage is green.
4. You have creative freedom to optimize the PostgreSQL database schema for maximum efficiency, utilizing JSONFields where appropriate for dynamic data. You do not need to strictly copy the legacy table designs.
5. You must enforce strict Python type hinting (`typing`) and linting across the entire codebase to maintain enterprise-grade readability and stability.

To begin, please confirm you have read the blueprint and understand these rules. Then, list out the exact sub-tasks you will complete for Step 1 (Initial Setup & Infrastructure). Wait for my approval before executing Step 1.
```
