"""Prompt service — versioned prompt template loading and rendering."""

from pathlib import Path

import yaml


class PromptService:
    def load_template(self, name: str = 'grounded_answer') -> dict:
        """Load versioned prompt template from registry."""
        path = Path(f'ml/prompts/{name}.yaml')
        return yaml.safe_load(path.read_text(encoding='utf-8'))

    def render_grounded_prompt(self, question: str, context: str) -> str:
        """Render final evidence-grounded prompt."""
        template = self.load_template()
        system_part = template['system']
        user_part = template['user'].format(question=question, context=context)
        return f'{system_part}\n\n{user_part}'
