"""IOA message template engine.

Reads message content from a TXT file and generates personalized messages by
replacing only the {{institute_name}} placeholder. The original template text
is never rewritten or paraphrased. UTF-8, line breaks, and punctuation are
preserved exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib


DEFAULT_PLACEHOLDER = "{{institute_name}}"


@dataclass
class TemplateResult:
    content: str
    placeholder: str
    has_placeholder: bool
    is_empty: bool
    preview: str  # first 200 characters


@dataclass
class GeneratedMessage:
    institute_name: str
    phone_number: str
    message: str
    message_hash: str  # SHA-256 of the exact message content
    preview: str


class MessageEngine:
    def __init__(self, placeholder: str = DEFAULT_PLACEHOLDER):
        self.placeholder = placeholder

    # ------------------------------------------------------------------ #
    # Template loading
    # ------------------------------------------------------------------ #
    def load_template(self, path: Path) -> TemplateResult:
        """Read the TXT template with UTF-8 encoding (no BOM stripping)."""
        text = path.read_text(encoding="utf-8")
        has_placeholder = self.placeholder in text
        preview = text[:200]
        return TemplateResult(
            content=text,
            placeholder=self.placeholder,
            has_placeholder=has_placeholder,
            is_empty=not text.strip(),
            preview=preview,
        )

    def validate_template(self, result: TemplateResult) -> list[str]:
        """Return validation warnings (not fatal)."""
        warnings: list[str] = []
        if result.is_empty:
            warnings.append("قالب الرسالة فارغ.")
        if not result.has_placeholder:
            warnings.append(
                f"العنصر النائب {self.placeholder} غير موجود في القالب — "
                "سيتم إرسال الرسالة نفسها لجميع المعاهد دون تخصيص."
            )
        return warnings

    # ------------------------------------------------------------------ #
    # Message generation
    # ------------------------------------------------------------------ #
    def generate(
        self,
        template_content: str,
        institute_name: str,
        phone_number: str,
    ) -> GeneratedMessage:
        """Replace only the institute-name placeholder; preserve everything else."""
        if not institute_name:
            raise ValueError("اسم المعهد غير مسموح أن يكون فارغاً.")

        personalized = template_content.replace(self.placeholder, institute_name)
        if not personalized.strip():
            raise ValueError("الرسالة الناتجة فارغة بعد التخصيص.")

        message_hash = hashlib.sha256(personalized.encode("utf-8")).hexdigest()
        preview = personalized[:200]

        return GeneratedMessage(
            institute_name=institute_name,
            phone_number=phone_number,
            message=personalized,
            message_hash=message_hash,
            preview=preview,
        )

    def detect_missing_placeholder(
        self, template_content: str
    ) -> bool:
        return self.placeholder not in template_content
