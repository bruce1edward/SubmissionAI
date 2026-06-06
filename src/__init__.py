"""SubmissionAI — multi-agent eCTD readiness analysis package."""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("submissionai")
except PackageNotFoundError:
    __version__ = "0.1.0"
