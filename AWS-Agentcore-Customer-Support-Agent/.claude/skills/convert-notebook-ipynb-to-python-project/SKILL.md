---
name: convert-notebook-ipynb-to-python-project
description: Convert Jupyter notebooks to production-ready Python projects. Broken into 4 explicit sequential steps with required outputs per step: (1) Validate inputs and return a manifest listing required files; (2) Transform code with explicit handling for Colab-specific calls, secrets, and large files; (3) Create a complete project structure with dependencies, tests, and platform-specific documentation; (4) Return reconstructed file tree and source code so users can recreate locally. Handles edge cases including google.colab imports, environment variables, cross-platform dependencies, GPU requirements, and ambiguous Colab-to-local replacements.
---

# Instructions

## Step 1: Validate Inputs & Build Manifest
First, check if you have all required inputs. One or more .ipynb notebooks will be attached. If the .ipynb files are not provided, ask for them. Specify the number and filenames received (e.g. 'Attached: analysis.ipynb, preprocessing.ipynb'). If notebooks or supporting datasets are missing, respond with a manifest listing missing filenames and stop. Example: 'MISSING: train.csv not provided; cannot complete data-processing extraction.'

## Step 2: Analyze & Transform Code
Extract only reproducible, non-interactive Python code required to reproduce the main program flow and data processing. Exclude ephemeral exploratory cells and plotted-only visualization cells. Include helper functions, classes, and data-loading code.

**Colab-specific handling:** If notebooks contain Colab-only calls (e.g., `from google.colab import drive`, `%pip`, `%tensorflow_version`, or direct Drive mounts), replace them with local equivalents, remove magics, and document the changes in README.md. If replacement is ambiguous, include a fallback stub and instructions.

**Secrets handling:** If code references secrets, do not include them; add a config.example.json or .env.example file and document how to set environment variables.

**Large files:** For large external files, include a download script and instructions instead of bundling them.

## Step 3: Create Project Structure
Produce a runnable Python package with:
- A clear entrypoint script (CLI script or main.py)
- Modules organized under a package directory
- If the project has outputs, include a sample output directory with example results
- A requirements.txt with pinned versions (package==x.y.z)
- A README.md documenting setup and usage
- A .gitignore file
- Basic unit tests (if applicable)

Specify the exact Python version required (e.g., 'Python 3.10.8') and any platform-specific steps. If cross-platform, state 'Linux/macOS/Windows supported'.

**System dependencies:** If any dependencies require system packages (apt, brew) or specific hardware (GPU), list them explicitly in README with installation commands. Example: 'Requires libXYZ; on macOS run: `brew install libxyz`.'

## Step 4: Verify & Return Output
Provide a reconstructed project directory listing and the full text content for each file so the user can recreate the project locally. Include the file tree structure clearly. If you can run smoke-tests, run and return actual output; otherwise provide exact commands for the user to run and the expected outputs. Name the output directory `project-name/` where project-name reflects the notebook's purpose. Generate a zip file of the entire project structure and provide a download link if possible.