.PHONY: install provision smoke-test extract index pipeline run clean

# Install Python dependencies
install:
	pip install -r requirements.txt
	pip install --upgrade pip

# Provision Azure resources and generate .env
provision:
	python -m src.provision

# Run smoke test to validate environment
smoke-test:
	python -m src.smoke_test

# Run smoke test (skip API connectivity checks)
smoke-test-quick:
	python -m src.smoke_test --quick

# Extract data from PDFs, images, and SOPs
extract:
	python -m src.pipeline --steps extract

# Create index and upload embeddings
index:
	python -m src.pipeline --steps index

# Full pipeline: extract + index
pipeline:
	python -m src.pipeline

# Full pipeline with forced re-extraction
pipeline-force:
	python -m src.pipeline --force

# Start the Streamlit web app
run:
	streamlit run src/web/app.py

# Clean up Azure resources (destructive!)
clean-azure:
	python -m src.provision --cleanup

# Verify all Azure resources are deleted
verify-cleanup:
	python -m src.provision --verify-cleanup

# Remove generated data
clean-data:
	rm -rf data/
