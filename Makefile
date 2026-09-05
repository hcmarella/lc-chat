.PHONY: dev up build push tf-plan tf-apply k8s

dev:
	cd backend && uvicorn app.main:app --reload --port 8000

up:
	docker compose up --build

build:
	docker build -f deploy/docker/Dockerfile.backend -t bizchat-backend:latest .
	docker build -f deploy/docker/Dockerfile.web -t bizchat-web:latest .

tf-plan:
	cd deploy/terraform && terraform init && terraform plan

tf-apply:
	cd deploy/terraform && terraform apply

k8s:
	kubectl apply -f deploy/k8s/
