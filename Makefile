.PHONY: up down logs ps rebuild prod-config

# Space-form `docker compose` (v2 plugin). No top-level `version:` key anywhere (D-09, RESEARCH SOTA).

up:            ## Build and start the full 6-service dev stack
	docker compose up -d --build

down:          ## Stop and remove the dev stack (volumes preserved)
	docker compose down

logs:          ## Follow logs (last 100 lines)
	docker compose logs -f --tail=100

ps:            ## Show service status incl. health
	docker compose ps

rebuild:       ## Rebuild images from scratch
	docker compose build --no-cache

prod-config:   ## Validate prod compose file (env vars must be set in your shell)
	POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD} docker compose -f docker-compose.prod.yml config --quiet
