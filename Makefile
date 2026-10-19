.PHONY: help install dev test lint type-check security docker-build docker-run compose-up compose-down up vm-host run mcp

# Default target
help:
	@echo "Alpha Sentinel MCP Server - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     - Install dependencies"
	@echo "  make venv        - Create virtual environment"
	@echo ""
	@echo "Development:"
	@echo "  make dev         - Start development server (port 8403)"
	@echo "  make mcp         - Run MCP stdio transport"
	@echo "  make docs        - Generate API documentation"
	@echo ""
	@echo "Testing:"
	@echo "  make test        - Run pytest suite"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        - Run Ruff linter"
	@echo "  make type-check  - Run MyPy type checking"
	@echo "  make security    - Run Bandit security scan"
	@echo ""
	@echo "Docker / Kubuntu VM:"
	@echo "  make compose-up   - API + Caddy on this machine"
	@echo "  make compose-down - Stop Compose stack"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run seller container (no spend key)"
	@echo "  make vm-host      - Print Kubuntu KVM host bootstrap command"
	@echo ""
	@echo "Production:"
	@echo "  make prod        - Deploy to Render/Vercel"
	@echo ""
	@echo "Clean:"
	@echo "  make clean       - Remove cache and build artifacts"

# Virtual Environment Setup
venv:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip

install: venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -e ".[dev]"

# Development Server
dev:
	@echo "Starting development server on port 8403..."
	.venv/bin/uvicorn app.application:app --reload --host 0.0.0.0 --port 8403 --log-level info

# MCP Stdio Transport
mcp:
	@echo "Starting MCP stdio transport..."
	.venv/bin/python run_stdio.py

# Run Production Server
run:
	.venv/bin/uvicorn app.application:app --host 0.0.0.0 --port 8403

# Testing
test:
	.venv/bin/pytest tests/ -v --tb=short

test-coverage:
	.venv/bin/pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing

test-watch:
	.venv/bin/pytest tests/ -v --tb=short -w tests/

# Code Quality
lint:
	.venv/bin/ruff check app/ tests/

type-check:
	.venv/bin/mypy app/ --ignore-missing-imports

security:
	.venv/bin/bandit -r app/ -ll

lint-fix:
	.venv/bin/ruff check app/ tests/ --fix

# Documentation
docs:
	.venv/bin/griffe --output docs/api-reference.md app/

# Docker / self-host
docker-build:
	docker build -t alpha-sentinel-mcp:latest .

docker-run:
	docker run --rm --name alpha-sentinel-mcp \
		-p 127.0.0.1:8403:8403 \
		-e HOST=0.0.0.0 \
		-e PORT=8403 \
		-e X402_PAY_TO_ADDRESS=${X402_PAY_TO_ADDRESS} \
		-e PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-http://127.0.0.1:8403} \
		alpha-sentinel-mcp:latest

compose-up:
	@test -f .env || cp .env.example .env
	docker compose up -d --build
	@echo "health: curl -fsS http://127.0.0.1:8403/health"

compose-down:
	docker compose down

up: compose-up

vm-host:
	@echo "sudo deploy/kubuntu/bootstrap-host.sh"
	@echo "SSH_PUBKEY=\$$HOME/.ssh/id_ed25519.pub deploy/kubuntu/create-vm.sh"
	@echo "See docs/KUBUNTU-VM.md"

docker-clean:
	docker rm -f alpha-sentinel-mcp 2>/dev/null || true

# Deployment
prod:
	@echo "Deploying to production..."
	@echo "1. Ensure all tests pass: make test"
	@echo "2. Push to main branch to trigger CI/CD"
	@echo "3. Dashboard will deploy to Vercel automatically"
	@echo "4. API will deploy to Render automatically"

# Clean
clean:
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml 2>/dev/null || true
	rm -rf dist/ *.egg-info 2>/dev/null || true
