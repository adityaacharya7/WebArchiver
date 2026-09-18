"""
Snapshot and content comparison service (Bonus Challenge).
Computes differences between versions/snapshots of a web page.
"""
import difflib
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DiffService:
    """Computes textual and structural differences between page versions."""

    @staticmethod
    def extract_clean_text(html_content: str) -> list[str]:
        """Extract line-separated clean text from HTML."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            # Remove scripts and styling
            for script in soup(["script", "style", "noscript"]):
                script.extract()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return lines
        except Exception:
            return [line.strip() for line in html_content.splitlines() if line.strip()]

    @staticmethod
    def compute_diff(text_a: str, text_b: str, from_label: str = "Snapshot A", to_label: str = "Snapshot B") -> dict:
        """
        Generate unified diff between two text/HTML contents.
        Returns summary statistics and formatted diff lines.
        """
        lines_a = DiffService.extract_clean_text(text_a)
        lines_b = DiffService.extract_clean_text(text_b)

        diff_lines = list(difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        ))

        additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        is_identical = len(diff_lines) == 0

        return {
            "is_identical": is_identical,
            "additions_count": additions,
            "deletions_count": deletions,
            "diff_lines": diff_lines,
            "diff_text": "\n".join(diff_lines),
        }
