import warnings

# Suppress non-actionable EOL deprecation notice for Python 3.11 from Google API client
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*Google will stop supporting.*")
warnings.filterwarnings("ignore", category=FutureWarning, module=r".*google\.api_core.*")
