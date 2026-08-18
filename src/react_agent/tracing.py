import logging
from os import getenv

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def enable_tracing():
    load_dotenv()
    tracking_uri = getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        logger.info("MLFLOW_TRACKING_URI not set, tracing disabled.")
        return

    try:
        import mlflow
        import mlflow.langchain
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "MLFLOW_TRACKING_URI is set but mlflow is not installed. "
            "Install it with: uv sync --extra tracing"
        ) from e

    try:
        mlflow.set_tracking_uri(tracking_uri)
        experiment_name = getenv("MLFLOW_EXPERIMENT_NAME", "default-agent-experiment")
        mlflow.set_experiment(experiment_name)
        mlflow.config.enable_async_logging()
        mlflow.langchain.autolog()
        logger.info("MLflow tracing enabled -> %s, experiment: %s", tracking_uri, experiment_name)
    except Exception as e:
        logger.warning("Failed to configure MLflow tracing: %s. Continuing without tracing.", e)
