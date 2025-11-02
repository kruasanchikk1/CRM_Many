# Voice2Action Constitution

## Core Principles

### I. AI-First Architecture
Voice2Action is an AI-powered platform focused on analyzing large audio files (up to 4 hours) from meetings, calls, or discussions. It performs transcription, analytics, summarization, and automated output generation:
- **OpenAI Whisper** for speech-to-text transcription (model: `whisper-1`, with chunking for large files to handle >30 minutes)
- **GPT-4o** for advanced content analysis, summarization (multi-level: brief, detailed, with quotes), task extraction, and style analysis (e.g., sales call feedback)
- AI responses must be structured (JSON for outputs) and actionable, with user-configurable prompts for customization
- Fallback mechanisms required for API failures (e.g., retry with exponential backoff, local caching for partial transcripts)
- All AI interactions must be logged for debugging, quality assurance, and usage analytics (e.g., processing time, token consumption)
- Support for user-selected analysis modes: meeting summary, task extraction, sales analytics, or custom

### II. Modular & Extensible Design
System components are independent, composable, and user-configurable to allow selection of tasks and services:
- **Backend**: Python 3.10+ with type hints (PEP 484), using FastAPI for API endpoints to handle user choices (e.g., select outputs: Excel, Word, Jira)
- **Telegram Bot**: Standalone module with python-telegram-bot, supporting user selection via commands or inline keyboards (e.g., /analyze [mode] [services])
- **Frontend**: Pure HTML/CSS/JS (no frameworks), fully responsive, mirroring bot functionality (upload audio, select task/service, view results)
- **Integrations**: Plugin-based architecture for Jira, Confluence, Google Docs/Sheets/Drive, Notion, with user-selected combinations
- Each module must be testable in isolation
- Clear interfaces between components (REST API for backend-frontend, message queues for async processing of large audio)
- User flow: Upload audio → Choose analysis task (transcription, summary, tasks) → Choose outputs (Excel tables, Word docs, Jira tickets) → AI processes and generates

### III. Security & Privacy by Default (NON-NEGOTIABLE)
User data protection is paramount, especially for 1-10 initial users with large audio files:
- **Environment variables**: All secrets in `.env` files (never committed)
- **API keys**: Rotated regularly, scoped to minimum permissions
- **.gitignore**: Must exclude `.env`, `*.log`, `temp_*`, API credentials, user audio files
- **Data retention**: Audio files deleted after processing (max 24h temp storage); generated outputs stored for 7 days with auto-cleanup
- **Encryption**: HTTPS/TLS for all API communications; encrypt stored audio (e.g., via AES if needed)
- **OAuth 2.0**: For third-party integrations (Jira, Google, Notion); users provide their own OAuth tokens/links for personal accounts
- **File handling**: All files created/stored on our side (Google Drive/Supabase); users can provide template links for customization, but AI fills automatically
- **User consent**: Explicit agreement for audio processing; anonymize sensitive data (e.g., PII detection)

### IV. Test-Driven Quality
Testing ensures reliability and prevents regressions for small-scale (1-10 users) deployment:
- **Framework**: pytest with coverage ≥80%
- **Test types**: Unit tests (mocked AI), integration tests (real APIs in staging, including large audio chunks), E2E (bot/site workflows with simulated user choices)
- **Pre-commit**: Tests must pass before merge
- **CI/CD**: Automated testing on GitHub Actions, including load tests for 10 concurrent users
- **Mocking**: Use `responses` library for external API mocking (e.g., Jira creation, Google Drive uploads)

### V. Documentation & Code Clarity
Code must be self-explanatory and well-documented:
- **README.md**: Setup instructions, architecture diagrams (Mermaid for flows), API examples, user guide for selecting tasks/services
- **Docstrings**: Google-style docstrings for all functions/classes
- **Type hints**: Mandatory for function signatures
- **Comments**: Explain "why", not "what" (code explains "what")
- **Changelog**: Track breaking changes in CHANGELOG.md
- **User docs**: Inline help for bot/site (e.g., how to choose tasks/outputs)

## Technical Standards

### Backend (Python)
- **Version**: Python 3.10+ (for modern type hints and async)
- **Dependencies**: Managed via `requirements.txt` with pinned versions (e.g., fastapi, uvicorn, openai, google-api-python-client, atlassian-python-api, notion-client, openpyxl)
- **Code style**: PEP 8 (black formatter, flake8 linter)
- **Async**: Use `asyncio` for I/O-bound operations (audio processing, API calls)
- **Error handling**: Explicit try-except blocks, log all errors, user-friendly messages
- **Logging**: Structured logging with `logging` module (INFO, WARNING, ERROR); include user_id for 1-10 users

### Frontend (Website)
- **Stack**: Pure HTML5, CSS3, vanilla JavaScript (ES6+), with forms for audio upload, task/service selection (checkboxes/dropdowns)
- **Responsive**: Mobile-first design, tested on iOS/Android; same functionality as bot (upload + process)
- **Performance**: <3s load time, lazy-load images; chunked uploads for large audio
- **Accessibility**: WCAG 2.1 AA compliance (alt text, ARIA labels)
- **Browser support**: Chrome, Firefox, Safari, Edge (last 2 versions)
- **No frameworks**: Keep it simple and fast; JS for async processing (fetch to backend)

### Telegram Bot
- **Library**: python-telegram-bot v20.7
- **Handlers**: Command handlers (`/start`, `/analyze`), message handlers (voice/audio); inline keyboards for task/service selection
- **Error recovery**: Graceful degradation on AI/API failures
- **Rate limiting**: Max 10 requests/minute per user (for 1-10 users)
- **Uptime**: 99.5% target (monitored via UptimeRobot)

### Integrations
- **Jira**: REST API v3, OAuth 2.0 (user provides token if personal; simulate for testing since no real Jira yet)
- **Confluence**: REST API, create pages in designated spaces (user provides space key)
- **Google Docs/Sheets/Drive**: Google Drive API v3 for real creation/filling (OAuth, auto-generate Docs for summaries, Sheets for tables; share links)
- **Notion**: Official API, create database entries/pages (user provides database ID)
- **Excel/Word**: Generate via `openpyxl` (Excel tables), `python-docx` (Word protocols); upload to Drive and share
- **File creation**: AI creates/fills all files automatically on our side; users can provide template links for customization (e.g., "use my Excel template")

## Development Workflow

### Git Strategy
- **Branching**: `main` (production), `dev` (staging), feature branches (`feature/task-name`)
- **Commits**: Conventional Commits format (`feat:`, `fix:`, `docs:`, `test:`)
- **Pull Requests**: Required for `main`, at least 1 approval
- **Tagging**: Semantic versioning (v1.0.0, v1.1.0, etc.)

### Deployment
- **Backend/Bot**: Render.com (free tier, always-on worker for 1-10 users)
- **Website**: GitHub Pages (static hosting)
- **Storage**: Google Drive for files (auto-creation/sharing), Supabase for user metadata (choices, logs)
- **Staging**: Separate environment for testing integrations
- **Rollback**: Keep last 3 versions deployable

### Monitoring & Observability
- **Logs**: Centralized logging (stdout → Render logs); track user selections and processing
- **Metrics**: Track processing time, API call counts, error rates (for large audio)
- **Alerts**: Notify on bot downtime or API quota exceeded
- **User feedback**: `/feedback` command in bot for bug reports; site form

## Project-Specific Rules

### Audio Processing Pipeline
1. **Input**: Voice message, audio file (MP3, OGG, M4A, up to 4 hours); chunking for large files
2. **Transcription**: Whisper API (parallel chunks for speed)
3. **Analysis**: GPT-4o prompt engineering for:
   - Summary generation (multi-level)
   - Task extraction (format: `- Задача: [Description] [Deadline] [Assignee]`)
   - Table filling (Excel: rows for tasks/calls)
   - Document generation (Word: formatted protocol with sections)
   - Sales call analysis (optional module)
4. **Output**: Structured JSON + files; auto-create in selected services
5. **Cleanup**: Delete temp audio files immediately after processing; outputs stored 7 days

### Telegram Bot Commands
- `/start`: Welcome + quick start guide
- `/analyze`: Start analysis with inline selection (task + services)
- `/help`: Feature list + examples
- `/feedback [text]`: Send feedback
- Voice/Audio: Automatic prompt for selection → processing

### Website Content Strategy
- **Landing page**: Hero section, benefits, how it works (upload + select), testimonials
- **Features page**: Detailed (transcription, summary, integrations); demo with selection
- **Pricing page**: Free (1-10 users), Team, Business (990₽, 3990₽)
- **Contact page**: Form + team contacts
- **Core**: Mirror bot — upload audio, select task/service, get results (async via backend)

### Error Handling Protocol
- **Graceful failures**: Never crash, always return user-friendly error
- **Retry logic**: 3 retries for API calls (exponential backoff)
- **User notifications**: "Обработка заняла больше времени, попробуйте позже"
- **Logging**: ERROR level for failures, include user_id and timestamp

## Quality Gates

### Before Merge (PR Checklist)
- [ ] All tests pass (`pytest -v`)
- [ ] Coverage ≥80% (`pytest --cov`)
- [ ] Code formatted (`black .`)
- [ ] Linter clean (`flake8 .`)
- [ ] No secrets in code (checked via `git-secrets`)
- [ ] Documentation updated (if API changed)

### Before Deploy
- [ ] Integration tests pass in staging (large audio, selections)
- [ ] Bot responds to `/start` within 2 seconds
- [ ] Website loads in <3 seconds
- [ ] All external APIs reachable (Jira sim, Google, Notion)
- [ ] Error tracking enabled (Sentry or similar)

## Governance

### Constitution Authority
This constitution supersedes all other development practices. Changes require:
1. Documented proposal with rationale
2. Team review and approval
3. Migration plan for existing code

### Amendment Process
- **Proposal**: Open GitHub Issue with `constitution-amendment` label
- **Review**: Minimum 48-hour discussion period
- **Approval**: Majority vote from core team
- **Implementation**: Update this document + CHANGELOG.md

### Compliance
- All code reviews must verify constitution compliance
- Violations require justification or refactoring
- Regular audits (monthly) to ensure adherence

---

**Version**: 1.1.0  
**Ratified**: 2025-11-02  
**Last Amended**: 2025-11-02  
**Next Review**: 2025-12-02

---

## Quick Reference

| Aspect | Standard |
|--------|----------|
| **Language** | Python 3.10+ |
| **AI Models** | Whisper-1, GPT-4o |
| **Testing** | pytest, ≥80% coverage |
| **Security** | .env files, OAuth 2.0, 7-day cleanup |
| **Deployment** | Render.com (backend/bot), GitHub Pages (site), Supabase (DB) |
| **Documentation** | Docstrings, README, CHANGELOG, user guide |
| **Code Style** | PEP 8, black, flake8 |
| **Bot Uptime** | 99.5% target |
| **Users** | Optimized for 1-10 (scalable) |