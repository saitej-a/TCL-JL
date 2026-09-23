.PHONY: up down vol-del logs ps rebuild prod-config prod-up prod-down prod-logs

# Space-form `docker compose` (v2 plugin). No top-level `version:` key anywhere (D-09, RESEARCH SOTA).

up:            ## Build and start the full 6-service dev stack
	docker compose up -d --build

down:          ## Stop and remove the dev stack (volumes preserved)
	docker compose down

Vol-del:
	docker

logs:          ## Follow logs (last 100 lines)
	docker compose logs -f --tail=100

ps:            ## Show service status incl. health
	docker compose ps

rebuild:       ## Rebuild images from scratch
	docker compose build --no-cache

prod-config:   ## Validate prod compose file (env vars must be set in your shell)
	POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD} docker compose -f docker-compose.prod.yml config --quiet

# Prod targets read credentials from .env.prod (gitignored; see .env.prod.example).
# -p is MANDATORY: a bare `-f docker-compose.prod.yml` merges with docker-compose.yml.
PROD_ARGS := -f docker-compose.prod.yml -p tcsjl-prod --env-file .env.prod

prod-up:       ## Build and start the prod topology (reads .env.prod)
	docker compose $(PROD_ARGS) up -d --build

prod-down:     ## Stop the prod stack (volumes preserved)
	docker compose $(PROD_ARGS) down

prod-logs:     ## Follow prod logs (last 100 lines)
	docker compose $(PROD_ARGS) logs -f --tail=100
