# NEXT AGENT INSTRUCTIONS

## How to respond to me

- Be direct and practical.
- Do not invent project structure, APIs, components, framework behaviour, or implementation details.
- Inspect the supplied repository context before making recommendations.
- When implementation work is requested, provide complete working files or a downloadable ZIP with correct project-relative paths.
- Do not provide partial snippets unless I explicitly request them.
- Do not repeatedly ask for context that can be extracted from the supplied files.
- Use the existing Neo project conventions and components where possible.
- Distinguish clearly between:
  1. verified repository facts;
  2. recommendations;
  3. assumptions requiring confirmation.
- For commands, prefer one complete copy-paste-safe PowerShell command.
- For visual work, prioritize professional layout, hierarchy, responsiveness, animation, and practical usability.
- Do not claim something is complete unless it has been checked against the actual code.
- When researching libraries, dashboards, or external products, search current official documentation and verify licensing, hosting model, framework compatibility, and integration requirements.

## Project overview

This is the Neo Tuckshop tutorial application.

Project root:

C:\Clients\Neo\Tutorials\Tuckshop

Technology:

- Frontend: React and TypeScript
- Frontend framework: Singular Systems Neo React / Neo Core
- Backend: .NET
- Architecture: Neo-style domain models, generated API clients, query services, command services, views, view models, controllers, and shared domain types
- Repository currently contains both client and server projects

The application is evolving from the standard tutorial into a more complete tuckshop / point-of-sale and management system.

Existing or planned functional areas include:

- product catalogue;
- recipes and ingredient-backed products;
- inventory and stock validation;
- customer management;
- customer wallets and payment methods;
- customer-facing ordering;
- order placement;
- order fulfilment;
- cancellation with inventory restoration;
- payment and VAT summaries;
- date-based order filtering;
- future reporting and management dashboards.

## Completed Orders fulfilment work

The Orders fulfilment screen has been substantially redesigned and is considered complete for now.

Completed behaviour includes:

- professional receipt-style fulfilment slips;
- responsive three-column desktop layout;
- two-column and single-column responsive fallbacks;
- one continuous receipt surface;
- torn-paper top and bottom edges;
- collapsed and expanded receipt states;
- clicking the receipt expands or collapses it;
- one normal receipt expanded at a time;
- pending, completed, and cancelled states;
- pending-order waiting-time indicators;
- urgency styling based on waiting duration;
- complete and cancel icon controls;
- pinning pending orders;
- pinned orders sort first;
- pinned state persisted in local storage;
- pins removed automatically when completed or cancelled;
- completion and cancellation transitions;
- completed receipt marking;
- cancelled receipt X marking;
- order search;
- status filters;
- From/To date-range filtering;
- order item quantities displayed using the `Product @ quantity` format;
- duplicate product and total information removed;
- compact collapsed summary with item count and total;
- staggered receipt loading animation;
- custom Arno's Corner logo in the receipt header;
- removal of the redundant TUCKSHOP text;
- current logo size and positioning finalized.

Important Orders files:

- Client/Tuckshop.WebApp/src/Domain/Views/Orders/ViewOrdersView.tsx
- Client/Tuckshop.WebApp/src/Domain/Views/Orders/ViewOrdersVM.ts
- Client/Tuckshop.WebApp/src/Domain/Views/Orders/ViewOrders.css
- Client/Tuckshop.WebApp/src/Domain/Views/Orders/logo.svg
- Client/Tuckshop.WebApp/src/Domain/Models/Orders
- Server/Tuckshop.Domain/Tuckshop.Core/App/Services/OrdersCommandService.cs
- Server/Tuckshop.Domain/Tuckshop.Core/App/Services/OrdersQueryService.cs
- Server/Tuckshop.Domain/Tuckshop.Core/Models/Orders
- relevant Orders controllers and generated API clients

Do not restart or redesign Orders unless explicitly asked.

## Next task: reporting dashboard

The next area is the reporting and analytics dashboard.

Before proposing implementation:

1. Search the repository for existing:
   - Neo chart components;
   - dashboard views;
   - reporting components;
   - card or metric components;
   - data-grid components;
   - visualization wrappers;
   - existing dependencies such as Chart.js, Recharts, Highcharts, ApexCharts, ECharts, Plotly, Syncfusion, Telerik, or similar;
   - existing reporting API endpoints;
   - query services that already expose useful aggregate data;
   - existing authentication and authorization rules for reports.

2. Determine whether the project already provides reusable Neo-native dashboard or chart patterns.

3. Map the existing backend data that can support reporting, including:
   - revenue;
   - order counts;
   - completed, pending, and cancelled orders;
   - product sales;
   - product quantities;
   - customer spending;
   - wallet activity;
   - payment types;
   - stock levels;
   - low-stock products;
   - recipe ingredient usage;
   - VAT;
   - daily, weekly, monthly, and custom date ranges;
   - fulfilment duration;
   - cancellation reasons;
   - inventory adjustments.

4. Identify which metrics can be produced from existing endpoints and which require new aggregate/reporting endpoints.

5. Research current external dashboard tools that could connect to this API and provide live graphs and configurable reporting.

Potential categories to investigate:

- embedded business-intelligence platforms;
- self-hosted dashboard builders;
- low-code internal tools;
- API-driven charting libraries;
- headless analytics layers;
- managed BI platforms.

Potential products may include tools such as Metabase, Apache Superset, Grafana, Power BI Embedded, Looker Studio, Retool, Appsmith, ToolJet, Redash, Evidence, Cube, Lightdash, and React chart libraries. Do not recommend these automatically. Verify whether each tool actually fits this project.

For every external option, evaluate:

- direct REST API support;
- GraphQL support where applicable;
- whether it requires direct database access;
- real-time or refresh behaviour;
- embedding inside React;
- authentication and row-level security;
- self-hosted versus managed;
- pricing and licensing;
- setup complexity;
- custom branding;
- export support;
- ability to build arbitrary graphs and filters;
- suitability for a small application;
- suitability for production;
- compatibility with a .NET backend and React frontend.

## Required first response from the next agent

After reading the context, return:

1. a verified summary of the existing reporting-related project capabilities;
2. a list of existing reusable Neo components or dependencies found;
3. existing backend endpoints and data relevant to reporting;
4. reporting gaps;
5. three realistic implementation routes:
   - fully native Neo/React dashboard;
   - embedded/self-hosted dashboard tool;
   - managed external BI tool;
6. a comparison table;
7. a recommended route for this project;
8. the exact files likely to be changed;
9. the next context command only if more repository information is genuinely required.

Do not modify code during the initial review.
Do not create a report file unless explicitly asked.
Return the review directly in chat.
