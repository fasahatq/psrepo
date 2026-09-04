"""Perfect Store AI Workbench — FastAPI backend.

A thin API layer over the existing pipeline (`pipeline.run_pipeline`),
the run artifacts in `outputs/<timestamp>/`, and the LLM client
(`agents.llm_client.call_llm`). The Streamlit GUI in `gui/` is untouched.
"""
