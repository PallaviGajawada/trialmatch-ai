# TrialMatch AI

**Multi-Agent Patient Eligibility Matching for Clinical Trials**

## Overview

TrialMatch AI is a research prototype that evaluates patient records against clinical trial eligibility criteria. It uses specialized agents to assess demographics, clinical measurements, and exclusion conditions, then combines the results into an explainable screening report.

## Core Features

- Patient and clinical-trial data ingestion
- Structured eligibility criteria
- Specialized eligibility agents
- PASS, FAIL, and UNKNOWN criterion outcomes
- Explainable matching results
- Researcher review workflow
- Dashboard for exploring patients, trials, and screening results

## Technology Stack

- Python
- Pandas
- ClinicalTrials.gov API
- FastAPI
- Streamlit
- Pytest
- Git and GitHub

## Project Structure

- `data/`: patient and trial datasets
- `src/`: data processing, agents, and matching logic
- `dashboard/`: user interface
- `tests/`: unit and integration tests
- `docs/`: architecture and development documentation

## Safety and Scope

This is a research and educational prototype, not a medical decision-making system. All matching results require appropriate human review. Initial patient records and test cases will use synthetic data.

## Team Workflow

Team members develop in separate feature branches and merge changes through pull requests into `main`.
