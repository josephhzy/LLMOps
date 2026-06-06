class ModelRouter:
    """Select the correct backend/model for a given task."""

    def route(self, task_type: str) -> str:
        # Scaffolding for planned task types — no callers pass these yet
        if task_type == 'multimodal_qa':
            return 'vision-main'
        if task_type == 'longform_reasoning':
            return 'text-large'
        return 'text-main'  # scaffolding label — not a real model ID; GenerationService composes this into model_version (e.g. 'text-main:template' or 'text-main:{llm_model_name}')
