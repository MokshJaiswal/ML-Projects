# CCRA — Canadian Credit Risk Analytics
#
# `make all` takes a fresh clone to a built warehouse, a tested star schema and
# Power BI extracts. Nothing else is required.

PYTHON  ?= python3
export PYTHONPATH := src
DBT_DIR := dbt/ccra
DBT     := dbt
DBT_ARGS := --profiles-dir .

.PHONY: help install ingest simulate load quality build test export all dashboard clean reset lint

help:                       ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	 | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:                    ## Install Python dependencies
	$(PYTHON) -m pip install -r requirements.txt

ingest:                     ## Fetch macro data (Bank of Canada + Statistics Canada)
	$(PYTHON) -m ccra.pipeline ingest

simulate:                   ## Generate the loan-level portfolio
	$(PYTHON) -m ccra.pipeline simulate

load:                       ## Load staged Parquet into DuckDB
	$(PYTHON) -m ccra.pipeline load

quality:                    ## Run the data quality gate (fails the build on error-severity breaches)
	$(PYTHON) -m ccra.pipeline quality

build:                      ## Build the dbt star schema
	cd $(DBT_DIR) && $(DBT) build $(DBT_ARGS)

test:                       ## Run dbt tests only
	cd $(DBT_DIR) && $(DBT) test $(DBT_ARGS)

docs:                       ## Serve the dbt documentation site with lineage graph
	cd $(DBT_DIR) && $(DBT) docs generate $(DBT_ARGS) && $(DBT) docs serve $(DBT_ARGS)

export:                     ## Export marts to Parquet + CSV for Power BI
	$(PYTHON) -m ccra.pipeline export

all: ingest simulate load quality build export   ## Full pipeline, end to end
	@echo ""
	@echo "Pipeline complete. Power BI extracts are in data/exports/."

dashboard:                  ## Launch the Streamlit dashboard
	streamlit run app/dashboard.py

clean:                      ## Remove generated data, keep the code
	rm -rf data/raw/* data/staged/* data/warehouse/* data/exports/* $(DBT_DIR)/target $(DBT_DIR)/logs

reset: clean all            ## Clean and rebuild from scratch
