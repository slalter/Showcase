With Cadenza, I have been building a docker/flask/socketio/celery app that handles multiple concurrent conversations and:
- generates reports in collaboration with the user
    - Generates sections, performs RAG, api calls, research, and generates graphics. Assigns those things to sections, with descriptions and titles.
    - User can view the report outline at any point.
    - The LLM follows user instructions, but also takes the initiative and a build first, ask later mentality.
    - When prompted, the LLM starts the report building process, where the sections and their appropriate information are sent out to separate LLMs to build. 
    - All the buttons and such in the UI are sent over by my backend and dynamically generated, including references, graphics, etc.
    - see: interactive_report_builder_screenshots
- integrates with tenant-specific RAG
- learns to use an API based on documentation and in-database prompt-based reinforement learning
    - Embeds error descriptions, clusters, comes up with PreventativeInstructions at an appropriate level (api, endpoint, tenant, general)
    - PIs are only generated if errors are repeated
    - PIs are compared and joined if similar
    - PIs are dynamically added to the prompt based on embeddings of the task that the LLM is working on vs previous failures
    - The effectiveness of the PIs is measured and there are API reports showing the historical success rate and existing PIs and associated ErrorTrackers
    - Ineffective PIs are removed
    - Some conditions lead to the admin being notified (LLM thinks that an error is due to an authentication issue)
    - All secrets are kept encrypted server-side and are injected into a persistent IPython environment that the LLM uses to retrieve data
    - and much much more.
    - see: sample_report, example_pi_report, apis

I built out the entire backend server myself in collaboration with a FE dev and his FE server.